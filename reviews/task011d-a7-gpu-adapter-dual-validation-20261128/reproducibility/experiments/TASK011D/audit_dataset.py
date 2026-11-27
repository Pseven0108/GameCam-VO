"""Route A: freeze the specified 19 midpoint windows, decode exact RGB only."""
import ast,csv,hashlib,io,json,math,shutil,types,zipfile,zlib
from pathlib import Path
import cv2,numpy as np,torch,yaml
from PIL import Image
from common import BASE,ROOT,TASK,csvwrite,dump,sha

FRESH=BASE/'experiments/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408'
EXPECTED=[('Day',29,1057),('Day',30,601),('Day',31,311),('Day',32,278),
 ('Sunset',12,737),('Sunset',13,91),('Sunset',15,336),('Sunset',16,234),
 ('Rain',38,448),('Rain',39,350),('Rain',40,870),('Snow',25,255),('Snow',26,277),
 ('Snow',27,590),('Snow',28,256),('Night',34,358),('Night',35,464),('Night',36,752),('Night',45,1005)]

def original_preprocessor():
    p=Path('D:/aaa/GameCam-VO-TASK009/external/DROID-W/src/utils/datasets.py')
    tree=ast.parse(p.read_text());cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='BaseDataset')
    selected=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('__init__','get_color','get_intrinsic')]
    minimal=ast.Module(body=[ast.ClassDef(name='BaseDataset',bases=[ast.Name(id='Dataset',ctx=ast.Load())],keywords=[],body=selected,decorator_list=[])],type_ignores=[])
    ast.fix_missing_locations(minimal)
    env=dict(torch=torch,cv2=cv2,np=np,math=math,Dataset=torch.utils.data.Dataset,
             focal2fov=lambda focal,pixels:2*math.atan(pixels/(2*focal)))
    exec(compile(minimal,str(p),'exec'),env)
    dump(TASK/'data/PREPROCESS_SOURCE_IDENTITY.json',dict(source=str(p),sha256=sha(p),
        method_ASTs_unmodified=['BaseDataset.__init__','BaseDataset.get_color','BaseDataset.get_intrinsic'],
        unused_model_dependencies_not_imported=True,device='cpu'))
    return env['BaseDataset']

def main():
    stage=json.loads((TASK/'reports/STAGE1_TEST_RESULTS.json').read_text())
    if stage['status']!='PASS' or not (TASK/'reports/TRANSFER_AUDIT.json').is_file():raise RuntimeError('Stage1 not accepted')
    out=TASK/'data';out.mkdir(exist_ok=False)
    private=TASK/'private/inputs';private.mkdir(parents=True,exist_ok=False)
    previous=ROOT/'experiments/TASK011C/data_audit_final/VALIDATION_SEQUENCE_ADMISSION.csv'
    candidates=list(csv.DictReader(previous.open(encoding='utf-8')))
    leftover=[r for r in candidates if r['used_in_TASK011B']=='False']
    eligible=[r for r in leftover if r['rgb_available_in_midpoint']=='True' and r['camera_mapping_exact']=='True'
        and float(r['window_K_max_deviation_px'])<.001 and float(r['GT_path_length_native_units'])>.0001]
    if len(leftover)!=27 or len(eligible)!=26:raise RuntimeError('Route A candidate counts changed')
    invalid=next(r for r in candidates if r['sequence']=='val_014')
    if invalid in eligible or float(invalid['GT_path_length_native_units'])>.0001:raise RuntimeError('val_014 exclusion failed')
    selected=[]
    for weather in ('Day','Sunset','Rain','Snow','Night'):
        own=sorted([r for r in eligible if r['environment']==weather],key=lambda r:r['sequence'])
        need=3 if weather=='Rain' else 4
        if len(own)<need:raise RuntimeError('Weather quota failure')
        selected.extend(own[:need])
    actual=[(r['environment'],int(r['sequence'][4:]),int(r['rgb_start'])) for r in selected]
    if actual!=EXPECTED:raise RuntimeError('Selection differs from explicitly approved 19 windows')
    windows=[]
    for r in selected:
        start=int(r['rgb_start']);seq=r['sequence']
        windows.append(dict(window_id=seq+f'_{start:05d}-{start+63:05d}',sequence=seq,environment=r['environment'],
            rgb_start=start,rgb_end=start+63,camera_start=start-1,camera_end=start+62,frames=64,stride=1,
            historical_full_sequence_baseline_exposure=True,TASK011B_exposure=False,blind_validation=False,route='A'))
    csvwrite(out/'SELECTED_19_WINDOWS.csv',windows)
    amendment=dict(route='A',previous_source_exclusion='ALL historical comparative sequences',
        amended_exclusion='TASK011B 20 sources only; historical full-sequence baseline exposure explicitly allowed',
        validation_total=47,TASK011B_excluded=20,remaining=27,technically_eligible=26,selected=19,
        val_014_GT_path=float(invalid['GT_path_length_native_units']),GT_path_threshold=.0001,
        weather_distribution=dict(Day=4,Sunset=4,Rain=3,Snow=4,Night=4),
        historical_exposure=True,blind_validation=False,selection_algorithm='ascending source ID then fixed midpoint; no algorithm metrics',
        selection_manifest_sha256=sha(out/'SELECTED_19_WINDOWS.csv'))
    dump(out/'DATA_POLICY_AMENDMENT.json',amendment)
    archives=BASE/'downloads/VIPER_RGB_JPG_ORIGINALS_20261119/archives'
    wanted={f"val/img/{r['sequence'][4:]}/{r['sequence'][4:]}_{f:05d}.jpg" for r in windows for f in range(r['rgb_start'],r['rgb_end']+1)}
    handles={p:zipfile.ZipFile(p) for p in sorted(archives.glob('val_img*.zip'))};index={}
    for p,z in handles.items():
        for info in z.infolist():
            if info.filename not in wanted:continue
            if info.filename in index:raise RuntimeError('Duplicate RGB identity')
            index[info.filename]=(p,z,info)
    if set(index)!=wanted:raise RuntimeError('Missing exact RGB members')
    torch.set_num_threads(2);cv2.setNumThreads(2);dataset=original_preprocessor()
    frozen=ROOT/'experiments/TASK011B/configs/frozen_r2.yaml'
    shutil.copy2(frozen,TASK/'configs/frozen_r2.yaml')
    cfg0=yaml.safe_load(frozen.read_text());image_rows=[];camera_rows=[];input_windows=[]
    try:
        for w in windows:
            wd=private/w['window_id'];rgb=wd/'rgb';rgb.mkdir(parents=True)
            ids=np.arange(w['rgb_start'],w['rgb_end']+1)
            gtpath=FRESH/'offline_gt'/(w['sequence']+'.npz')
            with np.load(gtpath,allow_pickle=False) as z:
                mapping={int(v):i for i,v in enumerate(z['rgb_ids'])};ix=[mapping[int(v)] for v in ids]
                cam=z['camera_ids'][ix].copy();gt=z['gt_c2w'][ix].copy();k=z['raw_intrinsics'][ix].copy()
            if not np.array_equal(cam,ids-1) or not np.isfinite(gt).all() or not np.isfinite(k).all():raise RuntimeError('GT pairing failed')
            span=float(np.max(np.abs(k-k[0])));path=float(np.linalg.norm(np.diff(gt[:,:3,3],axis=0),axis=1).sum())
            if span>=.001 or path<=.0001:raise RuntimeError('Technical window eligibility failed')
            k640=k[0].copy()/3;k640[2:]=(k[0,2:]+.5)/3-.5
            cfg=json.loads(json.dumps(cfg0));cfg['cam'].update(H=1080,W=1920,H_out=360,W_out=640,H_edge=0,W_edge=0,
                fx=float(k640[0]*3),fy=float(k640[1]*3),cx=float(k640[2]*3),cy=float(k640[3]*3))
            cfg['data']['input_folder']=str(rgb)
            stream=dataset(cfg,device='cpu');stream.color_paths=[]
            frames=[]
            for fid in ids:
                member=f"val/img/{w['sequence'][4:]}/{w['sequence'][4:]}_{fid:05d}.jpg"
                archive,z,info=index[member];raw=z.read(info)
                if zlib.crc32(raw)&0xffffffff!=info.CRC:raise RuntimeError('JPEG CRC mismatch')
                with Image.open(io.BytesIO(raw)) as im:
                    im.load()
                    if im.format!='JPEG' or im.mode!='RGB' or im.size!=(1920,1080):raise RuntimeError('RGB format/resolution invalid')
                    pixel_sha=hashlib.sha256(im.tobytes()).hexdigest()
                target=rgb/Path(member).name;target.write_bytes(raw)
                stream.color_paths=[str(target)]
                actual_tensor=stream.get_color(0)
                decoded=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
                resized=cv2.resize(decoded,(640,360),interpolation=cv2.INTER_LINEAR)
                expected_tensor=torch.from_numpy(resized).float().permute(2,0,1)[[2,1,0]].unsqueeze(0)/255.
                if not torch.equal(actual_tensor,expected_tensor):raise RuntimeError('Native R2 image preprocessing changed')
                np.testing.assert_allclose(stream.get_intrinsic().numpy(),k640,atol=5e-5,rtol=0)
                record=dict(window=w['window_id'],sequence=w['sequence'],rgb_id=int(fid),camera_id=int(fid)-1,
                    member=member,archive=str(archive),bytes=len(raw),crc32=f'{info.CRC:08x}',sha256=sha(target),
                    decoded_pixel_sha256=pixel_sha,decode='PASS',width=1920,height=1080,
                    native_R2_preprocess_bitwise_equal=True,
                    preprocessed_tensor_sha256=hashlib.sha256(actual_tensor.numpy().tobytes()).hexdigest())
                image_rows.append(record);frames.append(dict(rgb_id=int(fid),relative_path=target.relative_to(TASK).as_posix(),bytes=len(raw),sha256=sha(target)))
            np.savez_compressed(wd/'offline_gt.npz',rgb_ids=ids,camera_ids=cam,gt_c2w=gt,raw_intrinsics=k)
            camera_rows.append(dict(window=w['window_id'],frames=64,RGB_minus_1_exact=True,all_GT_finite=True,
                K_max_deviation_px=span,GT_path_length_native_units=path,source_GT_sha256=sha(gtpath),
                local_GT_sha256=sha(wd/'offline_gt.npz'),K640=json.dumps(k640.tolist()),native_intrinsics_match=True))
            input_windows.append(dict(**w,K_640x360=k640.tolist(),original_resolution_hw=[1080,1920],input_hw=[360,640],
                raw_GT=str((wd/'offline_gt.npz').relative_to(TASK)),frames_manifest=frames))
            print('ADMITTED_WINDOW',w['window_id'],flush=True)
    finally:
        for z in handles.values():z.close()
    csvwrite(out/'RGB_DECODE_AUDIT.csv',image_rows);csvwrite(out/'CAMERA_GT_AUDIT.csv',camera_rows)
    csvwrite(out/'HISTORICAL_EXPOSURE.csv',[dict(sequence=w['sequence'],historical_full_sequence_baseline_exposure=True,TASK011B_exposure=False,blind_validation=False,route='A') for w in windows])
    dump(TASK/'configs/GPU_INPUTS.json',dict(windows=input_windows,raw_GT_offline_only=True,
        historical_exposure=True,blind_validation=False,source='local original VIPER JPEG archives'))
    for name in ('DATA_POLICY_AMENDMENT.json','SELECTED_19_WINDOWS.csv'):
        shutil.copy2(out/name,TASK/'configs'/name)
    decision=dict(status='PASS_WITH_HISTORICAL_EXPOSURE',windows=19,RGB_decoded=len(image_rows),
        member_CRC_passed=len(image_rows),native_R2_image_preprocessing_equal=len(image_rows),
        camera_frames=19*64,GT_and_K_pass=True,GT_not_an_inference_input=True,route='A',
        full_archive_CRC_claimed=False,new_download_bytes=0,models_loaded=0,formal_SLAM_runs=0,
        selection_manifest_sha256=sha(out/'SELECTED_19_WINDOWS.csv'),RGB_audit_sha256=sha(out/'RGB_DECODE_AUDIT.csv'),
        camera_audit_sha256=sha(out/'CAMERA_GT_AUDIT.csv'),original_R2_YAML_sha256=sha(frozen))
    if len(image_rows)!=1216:raise RuntimeError('Incomplete RGB audit')
    dump(out/'DATA_ADMISSION_DECISION.json',decision);print(json.dumps(decision))

if __name__=='__main__':main()
