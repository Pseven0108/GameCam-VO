"""RGB-only segment contract (camera calibration allowed, pose labels local only)."""

import math
from pathlib import Path

import cv2
import numpy as np

from transfer_common import ENVIRONMENTS, SEGMENT_ID, digest, load

RAW = (1920, 1080)
OUT = (640, 360)
K_TOL = .001
BUFFER = 500


def scaled(k):
    factors = np.array([OUT[0]/RAW[0], OUT[1]/RAW[1]]*2)
    return np.asarray(k, dtype=np.float64)*factors + np.r_[0., 0., (factors[2:]-1)/2]


def virtual_k(ks):
    # Center the output; choose intrinsics that make all output rays land inside all original images.
    mid = (np.asarray(RAW)-1)/2
    # A half pixel margin keeps bilinear footprints valid in float32 as well.
    room = np.minimum(ks[:, 2:]-.5, np.asarray(RAW)-1.5-ks[:, 2:])
    if np.any(room <= 0):
        raise ValueError('virtual camera source center outside image')
    return np.r_[(ks[:, :2]*mid/room).max(axis=0), mid]


def remap_for(k_src, k_out):
    u = (np.arange(OUT[0])-k_out[2])/k_out[0]*k_src[0]+k_src[2]
    v = (np.arange(OUT[1])-k_out[3])/k_out[1]*k_src[1]+k_src[3]
    if u.min()<0 or v.min()<0 or u.max()>RAW[0]-1 or v.max()>RAW[1]-1:
        raise ValueError('virtual calibration would read outside source')
    return tuple(np.asarray(a, dtype=np.float32) for a in np.meshgrid(u,v))


def json_k(item):
    if (type(item) is not list or len(item)!=4 or
            any(type(x) not in (float,int) or not math.isfinite(x) for x in item) or min(item[:2])<=0):
        raise ValueError('invalid calibration')
    return np.asarray(item, dtype=np.float64)


def checked_manifest(path, require_rgb=False):
    doc = load(path)
    if set(doc) != {'id','sequence','environment','stride','raw_wh','out_wh','fps_nominal',
                    'branch','output_k','fixed_source_k','frames','protocol'}:
        raise ValueError('RGB manifest field allowlist violation')
    seg = doc['id']
    if (not SEGMENT_ID.fullmatch(seg) or not seg.startswith(doc['sequence']+'_') or
            doc['environment'] not in ENVIRONMENTS or doc['stride']!=1 or
            doc['raw_wh']!=list(RAW) or doc['out_wh']!=list(OUT) or doc['fps_nominal']!=15 or
            doc['protocol']!='DROIDW_VIPER_ZERO_SHOT_R1_V1'):
        raise ValueError('unexpected segment protocol')
    k = json_k(doc['output_k'])
    frames = doc['frames']
    start, end = map(int, seg.rsplit('_',1)[1].split('-'))
    if start < 1 or not frames or [f['rgb_id'] for f in frames] != list(range(start,end+1)):
        raise ValueError('discontinuous RGB identities')
    variable = doc['branch']=='VIRTUAL_K_DIRECT_REMAP'
    if not variable and doc['branch']!='FIXED_K_NATIVE_RESIZE':
        raise ValueError('unknown calibration branch')
    expect_fields = {'rgb_id','file','bytes','sha256','time_nominal_s'}|({'source_k'} if variable else set())
    np.testing.assert_allclose(k, scaled(json_k(doc['fixed_source_k'])), atol=1e-10, rtol=0)
    for f in frames:
        if (set(f)!=expect_fields or type(f['rgb_id']) is not int or f['file']!=f'{f["rgb_id"]:05d}.jpg' or
                type(f['bytes']) is not int or f['bytes']<=0 or len(f['sha256'])!=64 or
                any(ch not in '0123456789abcdef' for ch in f['sha256']) or
                abs(f['time_nominal_s']-(f['rgb_id']-1)/15)>1e-7):
            raise ValueError('invalid file identity or RGB manifest fields')
        if variable:
            src = json_k(f['source_k'])
            low = (np.array([0.,0.])-k[2:])/k[:2]*src[:2]+src[2:]
            high = (np.array(OUT)-1-k[2:])/k[:2]*src[:2]+src[2:]
            if np.any(low < 0) or np.any(high > np.array(RAW)-1):
                raise ValueError('unsupported source intrinsics or viewport')
        if require_rgb:
            p = Path(path).parent/f['file']
            if not p.is_file() or p.stat().st_size!=f['bytes'] or digest(p)!=f['sha256']:
                raise ValueError(f'RGB checksum mismatch: {p.name}')
    return doc


def selfcheck():
    k = np.array([1130.,1130.,959.5,539.5])
    np.testing.assert_allclose(scaled(k), [1130/3,1130/3,319.5,179.5])
    # Separate projection of known rays and inverse map, including offset centers and increased zoom.
    ks = np.array([k,[1420,1390,954.7,543.1]])
    kout = scaled(virtual_k(ks))
    for src in ks:
        x,y = remap_for(src,kout)
        for i,j in [(0,0),(323,123),(639,359)]:
            ray=(np.array([i,j])-kout[2:])/kout[:2]
            np.testing.assert_allclose([x[j,i],y[j,i]], src[:2]*ray+src[2:], atol=1.3e-4,rtol=0)
        # Check OpenCV's inverse-map sampling on independently constructed linear ramps.
        uv = np.dstack(np.meshgrid(np.arange(RAW[0],dtype=np.float32),np.arange(RAW[1],dtype=np.float32)))
        res=cv2.remap(uv,x,y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
        np.testing.assert_allclose(res,np.dstack((x,y)),atol=.0157,rtol=0)
    print('PASS: pixel centers, inverse projection, asymmetric virtual focal and bilinear viewport')


if __name__=='__main__':
    selfcheck()
