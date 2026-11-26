"""CPU-only utilities for the independent R2.2 audit. Never load model states."""
from __future__ import annotations
import csv, hashlib, json, os, pathlib, sys
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
PREV = ROOT.parent / 'task006a-r2-1-metric3d-gpu-pilot-20261126'
R2 = ROOT.parent / 'task006a-r2-depth-prior-reliability-20261126'
sys.path.insert(0, str(R2 / 'experiments/runtime_site'))

def cpu_only():
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise RuntimeError('Launch with CUDA_VISIBLE_DEVICES empty')

def sha(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def dump(path, value):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')

def csvwrite(path, rows):
    if not rows: raise ValueError('Empty table requires an explicit schema')
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with pathlib.Path(path).open('x', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fields); w.writeheader(); w.writerows(rows)

def records():
    result = []
    for sub in ['01_smoke/smoke_qualified', '02_pilot/pilot']:
        folder = PREV / sub
        receipt = json.loads((folder / 'INFERENCE_RECEIPT.json').read_text('utf-8'))
        assert receipt['status'] == 'PASS'
        for row in receipt['results']:
            row = dict(row)
            row['local_npz'] = folder / pathlib.PurePosixPath(row['output']).name
            if sha(row['local_npz']) != row['sha256']:
                raise RuntimeError('Sealed R2.1 inference output changed')
            result.append(row)
    assert len(result) == 16
    return result

def gt_dir(sequence):
    if sequence == '0000': return PROJECT / 'data/mvs_synth/GTAV_540/0000'
    if sequence == '0001': return PREV / 'inputs/MVS-Synth/GTAV_540/0001'
    raise ValueError('No new sequence/data acquisition authorized in this audit')

def depth(path):
    import OpenEXR
    with OpenEXR.File(str(path), separate_channels=True) as f:
        return f.channels()['Y'].pixels.copy().astype(np.float64)

def camera(path):
    d = json.loads(pathlib.Path(path).read_text('utf-8'))
    k = np.array([[d['f_x'],0,d['c_x']],[0,d['f_y'],d['c_y']],[0,0,1.]], dtype=float)
    return k, np.array(d['extrinsic'], dtype=float)

def array_sha(a):
    a = np.ascontiguousarray(a)
    return hashlib.sha256(a.dtype.str.encode() + str(a.shape).encode() + a.tobytes()).hexdigest()

def resize_bilinear(a, shape):
    """Float64 pixel-center bilinear, edge extension; matches align_corners=False geometry."""
    a = np.asarray(a, dtype=np.float64)
    if a.ndim != 2 or len(shape) != 2 or min(shape) < 1: raise ValueError('2D nonempty grids required')
    if not np.isfinite(a).all(): raise ValueError('Invalid network field; do not interpolate a GT mask')
    h,w = map(int, shape)
    y = np.maximum((np.arange(h)+.5)*a.shape[0]/h-.5, 0)
    x = np.maximum((np.arange(w)+.5)*a.shape[1]/w-.5, 0)
    y0 = np.minimum(np.floor(y).astype(int),a.shape[0]-1); y1 = np.minimum(y0+1,a.shape[0]-1)
    x0 = np.minimum(np.floor(x).astype(int),a.shape[1]-1); x1 = np.minimum(x0+1,a.shape[1]-1)
    wy = y-y0; wx = x-x0
    top = (1-wx)[None,:]*a[y0[:,None],x0] + wx[None,:]*a[y0[:,None],x1]
    bottom = (1-wx)[None,:]*a[y1[:,None],x0] + wx[None,:]*a[y1[:,None],x1]
    return (1-wy)[:,None]*top + wy[:,None]*bottom

def restore_bilinear(a, row):
    l,t,r,b = row['padding_ltrb']; h,w = row['canonical_hw']
    a = np.asarray(a)
    if a.shape != (h,w): raise ValueError('Canonical grid differs from receipt')
    cropped = a[t:h-b if b else h, l:w-r if r else w]
    if list(cropped.shape) != row['resized_hw']: raise ValueError('Padding/resize receipt mismatch')
    return resize_bilinear(cropped, row['sample']['input_hw'])

def resize_bilinear_float32(a, shape):
    """Match native float32 coordinate rounding, independently of PyTorch."""
    a=np.asarray(a,dtype=np.float32)
    if a.ndim!=2 or min(shape)<1 or not np.isfinite(a).all():raise ValueError('Finite 2D inputs only')
    h,w=map(int,shape)
    def grid(n,m):
        pos=(np.arange(m,dtype=np.float32)+np.float32(.5))*(np.float32(n)/np.float32(m))-np.float32(.5)
        pos=np.maximum(pos,np.float32(0));i0=np.minimum(np.floor(pos).astype(int),n-1);i1=np.minimum(i0+1,n-1)
        weight=np.clip(pos-i0.astype(np.float32),np.float32(0),np.float32(1))
        return i0,i1,weight
    y0,y1,wy=grid(a.shape[0],h);x0,x1,wx=grid(a.shape[1],w)
    top=(np.float32(1)-wx)[None,:]*a[y0[:,None],x0]+wx[None,:]*a[y0[:,None],x1]
    bottom=(np.float32(1)-wx)[None,:]*a[y1[:,None],x0]+wx[None,:]*a[y1[:,None],x1]
    return (np.float32(1)-wy)[:,None]*top+wy[:,None]*bottom

def restore_bilinear_float32(a,row):
    l,t,r,b=row['padding_ltrb'];h,w=row['canonical_hw']
    a=np.asarray(a)
    if a.shape!=(h,w):raise ValueError('Canonical shape mismatch')
    cropped=a[t:h-b if b else h,l:w-r if r else w]
    if list(cropped.shape)!=row['resized_hw']:raise ValueError('Receipt padding mismatch')
    return resize_bilinear_float32(cropped,row['sample']['input_hw'])
