"""Descriptive retained-source U/mask overlap; not per-iteration kernel weighting."""
import csv
import json
from pathlib import Path
import cv2
import numpy as np
from scipy.stats import spearmanr

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
roster={d['name']:d for d in json.loads((TASK/'private/DATA_MANIFEST.json').read_text())}
rows=[]
for run in sorted((TASK/'outputs/droid').glob('*_baseline_s43_r*')):
    if run.name=='night007_dev_baseline_s43_r1' or not (run/'receipt.json').exists():continue
    receipt=json.loads((run/'receipt.json').read_text())
    if receipt['status']!='COMPLETE':continue
    d=roster[receipt['dataset']]
    with np.load(run/'keyframes.npz',allow_pickle=False) as z:ids=z['rgb_ids'];u=z['uncertainties']
    for index,fid in enumerate(ids):
        native=np.clip(1/np.maximum(45*u[index]-35,.1),0,1)
        h,w=native.shape;yy,xx=np.mgrid[:h,:w].astype(np.float32)
        for model in ['pi3mos','gmos','geomotion','geomotion_full']:
            path=TASK/'outputs'/model/d['name']/f'{int(fid):05d}.npz'
            if not path.exists():continue
            with np.load(path,allow_pickle=False) as z:p=z['probability']
            mapx=(xx*8+.5)*p.shape[1]/d['hw'][1]-.5
            mapy=(yy*8+.5)*p.shape[0]/d['hw'][0]-.5
            m=cv2.remap(p,mapx,mapy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=0)
            external=1-.75*np.clip((m-.4)/.4,0,1)
            a=native<.999999;b=external<.999999
            correlation=float(spearmanr(u[index].ravel(),m.ravel()).statistic) if np.std(u[index])>1e-10 and np.std(m)>1e-10 else None
            rows.append({'dataset':d['name'],'rgb_id':int(fid),'model':model,
                'state':'retained_keyframes_after_Final_BA','source_U_mean':float(u[index].mean()),
                'native_source_UBA_mean':float(native.mean()),'native_source_attenuated_fraction':float(a.mean()),
                'external_source_only_attenuated_fraction':float(b.mean()),'both_attenuated_fraction':float((a&b).mean()),
                'external_without_native_source_attenuation_fraction':float((b&~a).mean()),
                'source_U_motion_score_Spearman_descriptive':correlation,
                'target_endpoint_included':False,'internal_round_weight_reconstruction':False,'motion_GT_available':False})
out=TASK/'01_failure_diagnosis/NATIVE_U_EXTERNAL_SOURCE_OVERLAP.csv'
with out.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('Measured',len(rows),'retained-source U/mask comparisons; no target-U or motion-GT claim')
