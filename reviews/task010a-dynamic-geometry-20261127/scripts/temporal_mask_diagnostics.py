"""Flow-warp consistency and geometry-disagreement proxies, explicitly not GT accuracy."""
import csv
import json
from pathlib import Path
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
cv2.setNumThreads(1)
rows=[]
for d in json.loads((TASK/'private/DATA_MANIFEST.json').read_text()):
    h,w=d['hw'];yy,xx=np.mgrid[:h,:w].astype(np.float32)
    for model in ['pi3mos','gmos','geomotion','geomotion_full']:
        base=TASK/'outputs'/model/d['name']
        if not base.exists() or not (base/'receipt.json').exists():continue
        if json.loads((base/'receipt.json').read_text())['status']!='COMPLETE':continue
        masks={}
        for fid in d['rgb_ids']:
            with np.load(base/f'{fid:05d}.npz',allow_pickle=False) as z:
                masks[fid]=cv2.resize(z['probability'],(w,h),interpolation=cv2.INTER_LINEAR)
        for i,j in zip(d['rgb_ids'][:-2],d['rgb_ids'][2:]):
            flow=TASK/'outputs/flows'/d['name']/f'{i:05d}_{j:05d}.npz'
            if not flow.exists():continue
            with np.load(flow,allow_pickle=False) as z:
                f=z['flow'];valid=z['valid'].copy();err=z['sampson_error'].copy()
            warp=cv2.remap(masks[j],xx+f[...,0],yy+f[...,1],cv2.INTER_LINEAR)
            a=masks[i]>.4;b=warp>.4;intersection=int((a&b&valid).sum());union=int(((a|b)&valid).sum())
            rigid_proxy=valid&(err<.5)
            rows.append({'dataset':d['name'],'model':model,'source_rgb':i,'target_rgb':j,
                'flow_valid_fraction':float(valid.mean()),
                'warped_score_absolute_difference_mean':float(np.mean(np.abs(masks[i][valid]-warp[valid]))) if valid.any() else None,
                'warped_mask_IoU':intersection/union if union else None,'empty_union':union==0,
                'dynamic_on_geometric_inlier_proxy_fraction':float(a[rigid_proxy].mean()) if rigid_proxy.any() else None,
                'proxy_is_not_static_GT':True,'accuracy_claim':False})
out=TASK/'03_candidate_inference/TEMPORAL_AND_GEOMETRY_PROXIES.csv'
with out.open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
print('Computed',len(rows),'flow-warp checks; empty-mask IoU undefined, never perfect by convention')
