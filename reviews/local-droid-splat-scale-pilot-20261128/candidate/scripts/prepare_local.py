"""Stage an immutable upstream export and exactly 64 local Train JPEGs."""
import argparse,csv, hashlib, io, json, pathlib, subprocess, tarfile, zipfile
import numpy as np
from PIL import Image

ROOT=pathlib.Path(__file__).resolve().parents[2]
TASK=ROOT/'candidate'
PROJECT=pathlib.Path('D:/aaa/GameCam-VO')
SOURCE=pathlib.Path('D:/aaa/GameCam-VO-TASK009/external/DROID-W')
COMMIT='c3414af6047d06bafc1a6645d09f23247f3b2cdc'

def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--moving-day004',action='store_true');args=ap.parse_args()
    dest=ROOT/'upstream/DROID-W'
    if not dest.exists():
        payload=subprocess.check_output(['git','-C',str(SOURCE),'archive',COMMIT])
        dest.mkdir()
        with tarfile.open(fileobj=io.BytesIO(payload)) as t:
            # git archive is a local committed tree, and no external tar is accepted.
            for m in t.getmembers():
                if m.isfile():
                    out=dest/m.name
                    if not out.resolve().is_relative_to(dest.resolve()):raise RuntimeError('Unsafe git member')
                    out.parent.mkdir(parents=True,exist_ok=True)
                    out.write_bytes(t.extractfile(m).read())
    branch=pathlib.Path('D:/aaa/GameCam-VO-TASK011B/experiments/TASK011B/CADP_DR_EXPERIMENTAL_BRANCH')
    candi=TASK/'native'
    candi.mkdir(exist_ok=True)
    native_receipt=[]
    for n in ['droid.cpp','droid_kernels.cu','correlation_kernels.cu','altcorr_kernel.cu']:
        original=dest/'src/lib'/n
        sealed=branch/'native'/('upstream_'+n+'.txt')
        if original.read_bytes().replace(b'\r\n',b'\n')!=sealed.read_bytes().replace(b'\r\n',b'\n'):
            raise RuntimeError('A5 original source does not match frozen c3414af6: '+n)
        out=candi/n
        data=(branch/'native'/n).read_bytes()
        if out.exists() and out.read_bytes()!=data:raise FileExistsError(out)
        if not out.exists():out.write_bytes(data)
        native_receipt.append(dict(file=n,original_sha256=sha(original),candidate_sha256=sha(out)))
    # A pre-existing Train development window, not any remote Validation run.
    seq='004' if args.moving_day004 else '001'
    ids=list(range(1658,1722)) if args.moving_day004 else list(range(309,373))
    case=f'train_{seq}_{ids[0]:05d}-{ids[-1]:05d}';data=TASK/'data'/case
    rgb=data/'rgb';rgb.mkdir(parents=True,exist_ok=True)
    archives=[PROJECT/'audits/VIPER_R1_A_15FRAME_CPU_PILOT_LOCAL_RECOVERY_V2/local_archives/train_img_00-19_2-9_jpg.zip',
              PROJECT/'audits/VIPER_R1_A_15FRAME_CPU_PILOT_LOCAL_RECOVERY_V2/local_archives/train_img_00-77_0_jpg.zip',
              PROJECT/'downloads/VIPER_RGB_JPG_ORIGINALS_20261119/archives/train_img_00-77_1_jpg.zip']
    records={}
    for archive in archives:
        with zipfile.ZipFile(archive) as z:
            for frame in ids:
                member=f'train/img/{seq}/{seq}_{frame:05d}.jpg'
                if member not in z.NameToInfo:continue
                info=z.getinfo(member);raw=z.read(info) # ZipFile validates member CRC.
                target=rgb/f'{seq}_{frame:05d}.jpg'
                if target.exists() and target.read_bytes()!=raw:raise RuntimeError('Conflicting image')
                target.write_bytes(raw)
                with Image.open(io.BytesIO(raw)) as im:
                    im.load()
                    if im.size!=(1920,1080) or im.mode!='RGB':raise RuntimeError('Image contract mismatch')
                records[frame]=dict(rgb_id=frame,camera_id=frame-1,filename=target.name,
                    bytes=len(raw),sha256=sha(target),zip_member=member,zip_crc32=f'{info.CRC:08x}',
                    source_archive=str(archive),full_decode_pass=True)
    if set(records)!=set(ids):raise RuntimeError('Missing exact Train RGBs '+str(set(ids)-set(records)))
    camera=PROJECT/'audits/VIPER_R0_1_TRAIN_AND_VO_PROTOCOL_AUDIT/02_metadata/train_camera.zip'
    with zipfile.ZipFile(camera) as z:
        rows={int(r['frame']):r for r in csv.DictReader(io.StringIO(z.read(f'train/camera/{seq}.csv').decode('utf-8-sig')))}
    # Freeze the upstream VIPER OpenGL -> OpenCV conversion already used by
    # the existing offline evaluator. GT is saved separately and never loaded
    # by the inference module.
    poses=[];intrinsics=[]
    change=np.diag([1.,-1.,-1.,1.])
    for frame in ids:
        r=rows[frame-1]
        view=np.array([[float(r[f'v{i}{j}']) for j in range(1,5)] for i in range(1,5)])
        proj=np.array([[float(r[f'p{i}{j}']) for j in range(1,5)] for i in range(1,5)])
        poses.append(np.linalg.inv(change@view))
        intrinsics.append([proj[0,0]*1920/2,proj[1,1]*1080/2,959.5,539.5])
    intrinsics=np.array(intrinsics)
    # Existing candidate C pixel-centre protocol; recorded, not silently refit.
    k=intrinsics.mean(axis=0)/3
    k[2:]=(intrinsics.mean(axis=0)[2:]+.5)/3-.5
    np.savez_compressed(data/'offline_gt.npz',rgb_ids=ids,camera_ids=np.array(ids)-1,
        gt_c2w=np.array(poses),raw_intrinsics=intrinsics)
    manifest=dict(window=case,split='Train',environment='Day',sequence=seq,
        frames=[records[i] for i in ids],K_640x360=k.tolist(),input_size=[360,640],stride=1,
        intrinsics_max_deviation_px=float(np.max(abs(intrinsics-intrinsics.mean(0)))),
        pixel_centres='C: half-pixel scaling, no crop',GT_for_offline_only=True,
        model_depth_units_not_certified_metres=True)
    (data/'INPUT_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    receipt=dict(source_commit=COMMIT,source_repository=str(SOURCE),exported_git_objects=True,
        droid_splat_commit='f0cb0316e1ee7f88f8a63c37a6fe19dd623e6eb2',
        shared_baseline_and_remote_unchanged=True,native_sources=native_receipt,
        frames=len(records),window=manifest['window'],K_640x360=k.tolist(),
        dependency_readonly_root=str(PROJECT/'baselines/droid_w/upstream'))
    receipt_path=TASK/'reports'/('STAGING_RECEIPT_DAY004.json' if args.moving_day004 else 'STAGING_RECEIPT.json')
    if receipt_path.exists():raise FileExistsError(receipt_path)
    receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
