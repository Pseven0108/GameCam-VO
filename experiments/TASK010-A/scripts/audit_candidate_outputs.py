"""Decode every saved prediction and check frame, shape, finite and SHA contracts."""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
ds=json.loads((TASK/'private/DATA_MANIFEST.json').read_text());rows=[]
for model in ['pi3mos','gmos','geomotion','geomotion_full']:
    for d in ds:
        folder=TASK/'outputs'/model/d['name']
        if not folder.exists():continue
        receipt=json.loads((folder/'receipt.json').read_text())
        if receipt['status']!='COMPLETE':raise ValueError('Incomplete admitted cache')
        hashes=json.loads((folder/'PREDICTION_SHA256.json').read_text())
        for fid in d['rgb_ids']:
            path=folder/f'{fid:05d}.npz'
            if hashlib.sha256(path.read_bytes()).hexdigest()!=hashes.get(path.name):raise ValueError('Prediction SHA mismatch')
            with np.load(path,allow_pickle=False) as z:
                if int(z['target_rgb_id'])!=fid:raise ValueError('Prediction identity mismatch')
                probability=z['probability']
                if probability.ndim!=2 or probability.min()<0 or probability.max()>1:raise ValueError('Invalid probability')
                for key in z.files:
                    array=z[key]
                    if array.dtype.kind in 'fc' and not np.isfinite(array).all():raise ValueError('Nonfinite auxiliary output')
                if 'depth' in z.files and not (z['depth']>0).all():raise ValueError('Nonpositive Pi3 auxiliary depth')
                rows.append({'model':model,'dataset':d['name'],'rgb_id':fid,'hw':list(probability.shape),'sha256':hashes[path.name],'status':'PASS'})
out=TASK/'09_reproducibility/CANDIDATE_OUTPUT_VALIDATION.json'
out.write_text(json.dumps({'status':'PASS','frames':len(rows),'checks':rows,'motion_GT_accuracy_verified':False},indent=2))
print('All',len(rows),'saved prediction arrays pass finite/identity/decode/SHA; no motion accuracy inference')
