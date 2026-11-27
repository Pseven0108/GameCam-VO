"""Check exact feature identity and native depth-prior positivity-mask preservation."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'


def main():
    rows=[]
    for d in json.loads((TASK/'private/DATA_MANIFEST.json').read_text()):
        if d['name']=='wildworld_thirdperson_qual':continue
        source=Path(d.get('prior_cache',TASK/'outputs/priors'/d['name']))
        blend=TASK/'outputs/priors_blend'/d['name']
        for fid in d['rgb_ids']:
            a=np.load(source/f'depth_{fid:05d}.npy',allow_pickle=False)
            b=np.load(blend/f'depth_{fid:05d}.npy',allow_pickle=False)
            mask_equal=np.array_equal(a>0,b>0)
            fa=hashlib.sha256((source/f'feature_{fid:05d}.npy').read_bytes()).hexdigest()
            fb=hashlib.sha256((blend/f'feature_{fid:05d}.npy').read_bytes()).hexdigest()
            if not mask_equal or fa!=fb or not np.isfinite(b).all():raise RuntimeError('Depth-candidate isolation violated')
            rows.append({'dataset':d['name'],'rgb_id':fid,'positive_depth_mask_identical':mask_equal,
                'feature_bytes_identical':fa==fb,'feature_sha256':fa,
                'changed_depth_pixel_fraction':float((a!=b).mean()),'native_mask_effect':'SOURCE_CONDITIONAL_NOT_CAPTURED_PER_BA',
                'full_trajectory_gradient_only_causal_effect_proven':False})
    with (TASK/'05_fusion_methods/depth_prior/DEPTH_INPUT_ISOLATION.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print('Depth input isolation PASS',len(rows),'frames; feature bytes and prior validity masks preserved')


if __name__=='__main__':main()
