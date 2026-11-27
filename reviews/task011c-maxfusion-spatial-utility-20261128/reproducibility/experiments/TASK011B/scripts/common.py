"""Task-local CPU IO. Historic assets are opened read-only and never rewritten."""
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT / 'experiments/TASK011B'
PREV = Path('D:/aaa/GameCam-VO-TASK011A')
PREV_TASK = PREV / 'experiments/TASK011A'
SOURCE = Path('D:/aaa/GameCam-VO/reviews/task006a-r2-1-metric3d-gpu-pilot-20261126')
PROTOCOL = json.loads((TASK / 'configs/r0_r1_protocol.json').read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(4*1024**2), b''):
            h.update(b)
    return h.hexdigest()


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def csvwrite(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text('', encoding='utf-8')
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_metrics():
    p = TASK / 'intake/reliability_metrics_frozen.py'
    spec = importlib.util.spec_from_file_location('task011b_frozen_metrics', p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def records():
    return json.loads((PREV_TASK / 'private/ASSET_INDEX.json').read_text())['records']


def load_historical_absrel(sample_id):
    path = PREV_TASK / 'runs/cpu_002/risk_maps' / (sample_id+'.npz')
    import numpy as np
    with np.load(path, allow_pickle=False) as z:
        return {k:z[k].copy() for k in z.files}
