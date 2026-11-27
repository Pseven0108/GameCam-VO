"""Use native predicted poses/depth, never GT, to explain camera-versus-flow residuals."""
import csv
import json
from pathlib import Path
import cv2
import numpy as np
from flow_geometry import camera_flow

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
ds={d['name']:d for d in json.loads((TASK/'private/DATA_MANIFEST.json').read_text())}
out=TASK/'04_geometry_residual/camera_residuals';out.mkdir(parents=True,exist_ok=True)
rows=[]
for run in sorted((TASK/'outputs/droid').glob('*_baseline_s43_r*')):
    if run.name=='night007_dev_baseline_s43_r1':continue  # superseded observer-version preliminary
    if not (run/'receipt.json').exists():continue
    receipt=json.loads((run/'receipt.json').read_text())
    if receipt['status']!='COMPLETE':continue
    d=ds[receipt['dataset']];directory=out/d['name'];directory.mkdir(exist_ok=True)
    with np.load(run/'keyframes.npz',allow_pickle=False) as z:
        ids=z['rgb_ids'].copy();poses=z['poses_w2c'].copy();disps=z['disps'].copy()
    k=np.load(Path(d['rgb_dir']).parent/'intrinsics.npy',allow_pickle=False)[0]/8
    for index in range(len(ids)-1):
        i,j=int(ids[index]),int(ids[index+1]);path=TASK/'outputs/flows'/d['name']/f'{i:05d}_{j:05d}.npz'
        if not path.exists():continue
        h,w=disps[index].shape
        with np.load(path,allow_pickle=False) as z:
            observed=z['flow'][::8,::8][:h,:w]/8
            fb=z['valid'][::8,::8][:h,:w]
            epi=z['sampson_error'][::8,::8][:h,:w]
        predicted,valid=camera_flow(disps[index],poses[index],poses[index+1],k)
        valid=valid&fb
        residual=np.linalg.norm(observed-predicted,axis=-1)*8 # tracker image pixels
        row={'dataset':d['name'],'source_rgb':i,'target_rgb':j,'state':'after_native_final_BA',
            'valid_fraction':float(valid.mean()),'disparity_floor_fraction':float((disps[index]<=1.00001e-5).mean()),
            'residual_median_px':float(np.median(residual[valid])) if valid.any() else None,
            'residual_p90_px':float(np.quantile(residual[valid],.9)) if valid.any() else None,
            'epipolar_error_median_px':float(np.median(epi[valid])) if valid.any() else None,
            'gt_used_in_camera_flow':False,'dynamic_accuracy_claim':False}
        rows.append(row)
        np.savez_compressed(directory/f'{i:05d}_{j:05d}.npz',observed_flow_feature_pixels=observed,
            camera_flow_feature_pixels=predicted,residual_image_pixels=residual,valid=valid,
            source_disp=disps[index],source_pose_w2c=poses[index],target_pose_w2c=poses[index+1])
        if index in (0,7,14):
            from PIL import Image,ImageDraw
            def rgb_flow(value):
                angle=np.arctan2(value[...,1],value[...,0]);magnitude=np.linalg.norm(value,axis=-1)
                hsv=np.zeros((*value.shape[:2],3),np.uint8)
                hsv[...,0]=np.uint8((angle+np.pi)/(2*np.pi)*179)
                hsv[...,1]=255;hsv[...,2]=np.uint8(np.clip(magnitude*16,0,255))
                return cv2.cvtColor(hsv,cv2.COLOR_HSV2RGB)
            heat=cv2.cvtColor(cv2.applyColorMap(np.uint8(np.clip(residual/8,0,1)*255),cv2.COLORMAP_TURBO),cv2.COLOR_BGR2RGB)
            heat[~valid]=[40,40,40]
            canvas=Image.new('RGB',(960,208),(15,15,15));draw=ImageDraw.Draw(canvas)
            for col,(array,title) in enumerate([(rgb_flow(observed),'RAFT observed flow'),(rgb_flow(predicted),'Native pose/depth camera flow'),(heat,'Residual, 0-8 image px; invalid gray')]):
                canvas.paste(Image.fromarray(array).resize((320,180)),(col*320,28));draw.text((col*320+4,5),title,fill='white')
            canvas.save(directory/f'{i:05d}_{j:05d}_flow.jpg',quality=90)
fields=list(rows[0]) if rows else []
with (TASK/'04_geometry_residual/CAMERA_FLOW_RESIDUAL_STATISTICS.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
print('Computed',len(rows),'native pose/depth versus RAFT residual maps without reading GT')
