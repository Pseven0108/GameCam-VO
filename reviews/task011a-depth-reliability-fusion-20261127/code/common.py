"""CPU-only TASK011A utilities; never import a model or alter historic caches."""
import csv,hashlib,importlib.util,json,os,sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
TASK=ROOT/'experiments/TASK011A'
SOURCE=Path('D:/aaa/GameCam-VO/reviews/task006a-r2-1-metric3d-gpu-pilot-20261126')
RESTORED=Path('D:/aaa/GameCam-VO/reviews/task006a-r2-2-depth-restoration-gt-audit-20261126')
HIST=SOURCE/'04_evaluation/diagnostic_zero_extension_002'
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['MPLCONFIGDIR']='D:/aaa/caches/matplotlib/task011a'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
sys.path.insert(0,str(TASK/'private/runtime_site'))

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024**2),b''):h.update(block)
    return h.hexdigest()

def dump(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def csvwrite(path,rows):
    if not rows:return
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def csvread(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def legacy():
    # Current Python3.11 needs its own isolated wheel. Loading the old cp39
    # reader failed before decoding; source EXR files were not modified.
    import OpenEXR
    sys.path.insert(0,str(TASK/'intake/legacy_code'))
    spec=importlib.util.spec_from_file_location('task011_original_evaluation',TASK/'intake/legacy_code/evaluate_pilot.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    m.ROOT=SOURCE
    return m

def records():
    rows=json.loads((TASK/'private/ASSET_INDEX.json').read_text(encoding='utf-8'))['records']
    return rows

def ground_truth(row):
    import OpenEXR
    sample=row['sample'];seq=sample['sequence_id'];fid=sample['frame_id']
    directory=Path('D:/aaa/GameCam-VO/data/mvs_synth/GTAV_540/0000') if seq=='0000' else SOURCE/'inputs/MVS-Synth/GTAV_540/0001'
    with OpenEXR.File(str(directory/'depths'/(fid+'.exr')),separate_channels=True) as f:
        gt=f.channels()['Y'].pixels.copy().astype(np.float64)
    return gt

def maps(row,variant='FROZEN_BICUBIC_ZERO_EXTENDED'):
    with np.load(row['local_npz'],allow_pickle=False) as z:
        confidence=z['native_confidence'].astype(np.float64)
        pred=z['native_depth'].astype(np.float64);flipped=z['flip_depth'][:,::-1].astype(np.float64)
    if variant=='R2_2_BILINEAR_SAME_FOCAL':
        with np.load(RESTORED/'02_restoration/torch_CPU'/(row['sample']['sample_id']+'.npz'),allow_pickle=False) as z:
            pred=z['native_bilinear_same_focal'].astype(np.float64)
            flipped=z['flip_bilinear_same_focal'][:,::-1].astype(np.float64)
    if not(pred.shape==flipped.shape==confidence.shape):raise ValueError('Pixel grid mismatch')
    if not (np.isfinite(pred).all() and np.isfinite(flipped).all() and np.isfinite(confidence).all()):raise ValueError('Nonfinite actual model field')
    if (pred<0).any() or (flipped<0).any():raise ValueError('Unapproved negative depth, do not silently filter')
    return pred,confidence,np.abs(pred-flipped)/(np.abs(pred)+1e-6),flipped

def cpu_assert():
    if 'torch' in sys.modules:raise RuntimeError('This experiment must not import PyTorch')
