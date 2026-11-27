"""Read an existing WildWorld clip for qualitative third-person transfer only."""
import hashlib
import json
from pathlib import Path
import cv2

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
path=Path('D:/aaa/GameCam-VO/GameCam-WW-V5_6/data/data_part1/vJlz_cbaSlaCYnpMbSg-AA/rgb.mp4')
ds=json.loads((TASK/'private/DATA_MANIFEST.json').read_text())
out=TASK/'private/datasets/wildworld_thirdperson_qual';(out/'rgb').mkdir(parents=True,exist_ok=False)
c=cv2.VideoCapture(str(path));c.set(cv2.CAP_PROP_POS_FRAMES,64);frames=[]
for fid in range(64,96):
    ok,image=c.read()
    if not ok:raise RuntimeError('Existing source video ended early')
    p=out/f'rgb/{fid:05d}.png';cv2.imwrite(str(p),image)
    frames.append({'rgb_id':fid,'original_video_zero_based_frame':fid,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
c.release()
h=hashlib.sha256()
with path.open('rb') as f:
    for block in iter(lambda:f.read(8*1024**2),b''):h.update(block)
ds.append({'name':'wildworld_thirdperson_qual','domain':'WILDWORLD_GAME_NOT_REAL','environment':'ThirdPersonGame',
    'split':'QUALITATIVE_ONLY_NO_ADMITTED_CAMERA_OR_MOTION_GT','sequence':'vJlz_cbaSlaCYnpMbSg-AA',
    'rgb_ids':list(range(64,96)),'rgb_dir':str(out/'rgb'),'image_suffix':'.png','hw':[216,384],
    'inference_only':True,'source_video_sha256':h.hexdigest(),'rgb_manifest':frames})
(TASK/'private/DATA_MANIFEST.json').write_text(json.dumps(ds,indent=2))
(TASK/'09_reproducibility/DATASET_WINDOWS.json').write_text(json.dumps([
    {k:v for k,v in row.items() if k not in ('rgb_dir','prior_cache','offline_gt')} for row in ds],indent=2))
print('Admitted 32 WildWorld frames for independent mask/flow inspection only; no fabricated K or GT')
