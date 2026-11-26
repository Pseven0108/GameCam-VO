"""Isolated evaluator prototype; this does not modify DROID-W's wrapper.

The only supported production-style operation is positive depth restoration.
Confidence is an unrestricted score and uses the generic interpolation utility.
"""
from common import np, restore_bilinear, restore_bilinear_float32, resize_bilinear

def restore_positive_depth(canonical,row,*,focal_convention='baseline',output_grid='input',arithmetic='float32',cap=300.):
    canonical=np.asarray(canonical)
    if canonical.ndim!=2 or not np.isfinite(canonical).all() or (canonical<=0).any():
        raise ValueError('Canonical depth must be finite and strictly positive; never fill or mask bad predictions')
    if not np.isfinite(row['sample']['fx']) or row['sample']['fx']<=0:raise ValueError('Positive focal required')
    if cap is not None and (not np.isfinite(cap) or cap<=0):raise ValueError('Invalid cap')
    if focal_convention not in ['baseline','official_resized']:raise ValueError('Unknown focal convention')
    if output_grid not in ['input','source']:raise ValueError('Unknown output pixel grid')
    if arithmetic=='float32':p=restore_bilinear_float32(canonical,row)
    elif arithmetic=='float64':p=restore_bilinear(canonical,row)
    else:raise ValueError('Unknown arithmetic')
    factor=row['sample']['fx']/1000.
    if focal_convention=='official_resized':factor*=row['resize_scale']
    # Resolution recovery does not multiply physical depth by the image resize.
    # The canonical focal conversion already describes the network input image.
    if output_grid=='source' and row['sample']['source_hw']!=row['sample']['input_hw']:
        p=resize_bilinear(p,row['sample']['source_hw'])
    p=p*np.asarray(factor,dtype=p.dtype)
    if cap is not None:p=np.minimum(p,cap)
    if not np.isfinite(p).all() or (p<=0).any():raise ValueError('Restored depth invalid; refuse silent repairs')
    return p

def pixel_center_resize_matrix(sx,sy):
    if not np.isfinite([sx,sy]).all() or min(sx,sy)<=0:raise ValueError('Positive image scales required')
    return np.array([[sx,0,.5*sx-.5],[0,sy,.5*sy-.5],[0,0,1.]],dtype=float)

def intrinsics_chain(K,source_hw,input_hw,resized_hw,padding_ltrb):
    K=np.asarray(K,dtype=float)
    if K.shape!=(3,3) or not np.isfinite(K).all():raise ValueError('Finite K required')
    sh,sw=source_hw;ih,iw=input_hw;rh,rw=resized_hw;l,t,r,b=padding_ltrb
    if min(sh,sw,ih,iw,rh,rw)<=0 or min(l,t,r,b)<0:raise ValueError('Invalid image geometry')
    m0=pixel_center_resize_matrix(iw/sw,ih/sh);m1=pixel_center_resize_matrix(rw/iw,rh/ih)
    pad=np.array([[1.,0,l],[0,1.,t],[0,0,1.]])
    return {'K_input':m0@K,'K_canonical':pad@m1@m0@K,'source_to_canonical':pad@m1@m0,
            'K_roundtrip':np.linalg.solve(pad@m1@m0,pad@m1@m0@K)}
