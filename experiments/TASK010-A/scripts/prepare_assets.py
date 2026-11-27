"""Admit matched exploratory windows, without supplying GT to inference."""
import csv
import io
import json
import hashlib
from pathlib import Path
import shutil
import zipfile
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT / 'experiments/TASK010-A'
MAIN = Path('D:/aaa/GameCam-VO')
OLD = Path('D:/aaa/GameCam-VO-TASK009')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()


def save(path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    manifest=[]
    # The development window was previously inspected; it is never held-out evidence.
    source=MAIN/'experiments/task008_pi3mos/retrieved/outputs/night007/original_rgb'
    prior=OLD/'experiments/TASK009/outputs/native_priors_216x384_r3'
    with np.load(prior/'offline_gt.npz',allow_pickle=False) as z:
        ids=z['rgb_ids'].copy();gt=z['c2w'].copy();k=z['intrinsics'].copy()
    dev=TASK/'private/datasets/night007_dev'
    (dev/'rgb').mkdir(parents=True,exist_ok=False)
    for fid in ids:shutil.copyfile(source/f'{fid:05d}.jpg',dev/f'rgb/{fid:05d}.jpg')
    np.savez_compressed(dev/'offline_gt.npz',rgb_ids=ids,c2w=gt,intrinsics=k)
    np.save(dev/'intrinsics.npy',k)
    manifest.append({'name':'night007_dev','domain':'VIPER_GAME','environment':'Night',
        'split':'DEVELOPMENT_PREVIOUSLY_INSPECTED','sequence':'val007','rgb_ids':ids.tolist(),
        'rgb_dir':str(dev/'rgb'),'prior_cache':str(prior),'offline_gt':str(dev/'offline_gt.npz'),
        'pose_unit':'VIPER game units, not verified metres','hw':[216,384]})
    historical=MAIN/'experiments/VIPER_R1_B2_0_CPU_320F_PREFLIGHT'
    records=list(csv.DictReader((historical/'FIVE_ENV_FRAME_MANIFEST_320.csv').open(encoding='utf-8-sig')))
    camera=MAIN/'audits/VIPER_R0_1_TRAIN_AND_VO_PROTOCOL_AUDIT/02_metadata/train_camera.zip'
    for env,seq in [('Day','004'),('Sunset','007'),('Rain','030'),('Night','008'),('Snow','032')]:
        rows=[r for r in records if r['environment']==env][:32]
        ids=np.array([int(r['RGB_frame_id']) for r in rows])
        name=f'{env.lower()}{seq}_holdout'
        out=TASK/'private/datasets'/name
        (out/'rgb').mkdir(parents=True,exist_ok=False)
        for r in rows:
            src=Path(r['original_path'])
            if sha(src)!=r['raw_JPEG_SHA256']:raise RuntimeError('Historical RGB hash mismatch')
            with Image.open(src) as im:
                im.load()
                if im.size!=(1920,1080):raise RuntimeError('RGB geometry mismatch')
            shutil.copyfile(src,out/f'rgb/{int(r["RGB_frame_id"]):05d}.jpg')
        with zipfile.ZipFile(camera) as archive:
            blob=archive.read(f'train/camera/{seq}.csv')
        cr={int(r['frame']):r for r in csv.DictReader(io.StringIO(blob.decode('utf-8-sig')))}
        poses=[];intr=[]
        for fid in ids:
            r=cr[int(fid)-1]
            v=np.array([[float(r[f'v{i}{j}']) for j in range(1,5)] for i in range(1,5)])
            p=np.array([[float(r[f'p{i}{j}']) for j in range(1,5)] for i in range(1,5)])
            poses.append(np.linalg.inv(v)@np.diag([1.,-1.,-1.,1.]))
            raw=np.array([1920*p[0,0]/2,1080*p[1,1]/2,1920*(1-p[0,2])/2,1080*(1+p[1,2])/2])
            s=np.array([384/1920,216/1080]*2)
            new=raw*s;new[2:]+=(s[2:]-1)/2
            intr.append(new)
        intr=np.array(intr)
        if np.max(np.abs(intr-intr[0]))>.001:raise RuntimeError('Variable K not admitted')
        np.savez_compressed(out/'offline_gt.npz',rgb_ids=ids,c2w=np.array(poses),intrinsics=intr)
        np.save(out/'intrinsics.npy',intr)
        manifest.append({'name':name,'domain':'VIPER_GAME','environment':env,'sequence':'train'+seq,
            'split':'HELD_OUT_FROM_TASK010A_PARAMETER_SELECTION_NOT_NEW_DATASET_TEST',
            'rgb_ids':ids.tolist(),'rgb_dir':str(out/'rgb'),'offline_gt':str(out/'offline_gt.npz'),
            'hw':[216,384],'pose_unit':'VIPER game units, not verified metres',
            'camera_member_sha256':hashlib.sha256(blob).hexdigest(),'mapping':'camera=RGB-1'})
    for entry in manifest:
        entry['rgb_manifest']=[{'rgb_id':fid,'sha256':sha(Path(entry['rgb_dir'])/f'{fid:05d}.jpg')} for fid in entry['rgb_ids']]
    save(TASK/'private/DATA_MANIFEST.json',manifest)
    public=[{k:v for k,v in row.items() if k not in ('rgb_dir','prior_cache','offline_gt')} for row in manifest]
    save(TASK/'09_reproducibility/DATASET_WINDOWS.json',public)
    print('Admitted',len(manifest),'windows;',sum(len(r['rgb_ids']) for r in manifest),'RGB frames')


if __name__=='__main__':main()
