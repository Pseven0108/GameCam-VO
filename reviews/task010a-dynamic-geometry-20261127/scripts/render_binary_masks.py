"""Lossless threshold0.4 masks for every admitted model/frame, derived from raw floats."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A';rows=[]
for d in json.loads((TASK/'private/DATA_MANIFEST.json').read_text()):
    for model in ['pi3mos','gmos','geomotion','geomotion_full']:
        source=TASK/'outputs'/model/d['name']
        receipt=json.loads((source/'receipt.json').read_text())
        if receipt['status']!='COMPLETE':raise RuntimeError('Incomplete prediction source')
        dest=TASK/'03_candidate_inference/binary_masks'/model/d['name'];dest.mkdir(parents=True,exist_ok=True)
        for fid in d['rgb_ids']:
            path=source/f'{fid:05d}.npz'
            with np.load(path,allow_pickle=False) as z:p=z['probability']
            mask=np.uint8(p>.4)*255;target=dest/f'{fid:05d}.png';Image.fromarray(mask).save(target)
            with Image.open(target) as image:
                if not np.array_equal(np.array(image),mask):raise RuntimeError('Binary mask decode differs')
            rows.append({'model':model,'dataset':d['name'],'rgb_id':fid,'threshold':.4,
                'source_npz_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'mask_path':target.relative_to(TASK).as_posix(),'mask_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                'fraction_gt02':float((p>.2).mean()),'fraction_gt04':float((p>.4).mean()),'fraction_gt06':float((p>.6).mean()),
                'thresholded_prediction_not_GT':True})
with (TASK/'03_candidate_inference/BINARY_MASK_INDEX.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('Saved and independently decoded',len(rows),'lossless binary masks')
