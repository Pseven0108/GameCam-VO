"""Validity-aware relative risk, not a probability or calibrated variance.

Undefined signals stay NaN. A separate maximum-risk rejection sentinel is used
only in full-GT policy diagnostics; invalid priors always have coefficient zero.
"""
import numpy as np
from scipy.stats import rankdata

DISAGREEMENTS = ('LegacyRelative','SymmetricRelative','LogDisagreement','AbsoluteDifference')
METHODS = ('NativeOnly','FlipOnly','RankFusion','MaxFusion','ValidityAwareFusion')


def fast_risk_coverage(error,risk):
    """Same expected within-tie prefixes as the frozen reference, vectorized."""
    e,s=np.asarray(error,dtype=np.float64).ravel(),np.asarray(risk,dtype=np.float64).ravel()
    if not len(e) or e.shape!=s.shape or not np.isfinite(e).all() or not np.isfinite(s).all() or (e<0).any():
        raise ValueError('Finite equal-length nonnegative errors and finite risks required')
    order=np.argsort(s,kind='stable');ss=s[order];ee=e[order]
    starts=np.r_[0,np.flatnonzero(ss[1:]!=ss[:-1])+1]
    lengths=np.diff(np.r_[starts,len(e)])
    sums=np.add.reduceat(ee,starts)
    previous=np.r_[0.,np.cumsum(sums)[:-1]]
    prefix=np.repeat(previous,lengths)+(np.arange(len(e))-np.repeat(starts,lengths)+1)*np.repeat(sums/lengths,lengths)
    k=np.arange(1,len(e)+1)
    curve=prefix/k;oracle=np.cumsum(np.sort(e))/k
    coverage=np.r_[0.,k/len(e)]
    curve=np.r_[curve[0],curve];oracle=np.r_[oracle[0],oracle];random=np.full(len(e)+1,e.mean())
    return dict(coverage=coverage,risk=curve,oracle=oracle,random=random,
                AUSE_raw_AbsRel=float(np.trapezoid(curve-oracle,coverage)),
                AURG_raw_AbsRel=float(np.trapezoid(random-curve,coverage)))


def validity(native, flip_aligned, tta_valid, depth_min=1e-6):
    a = np.asarray(native, dtype=np.float64)
    b = np.asarray(flip_aligned, dtype=np.float64)
    original = np.asarray(tta_valid)
    if a.ndim != 2 or a.shape != b.shape or a.shape != original.shape:
        raise ValueError('Native, horizontally unflipped flip and tta_valid grids must agree')
    if original.dtype != bool:
        raise ValueError('The original tta_valid must be boolean, not a numeric proxy')
    if not np.isfinite(depth_min) or depth_min < 0:
        raise ValueError('Invalid numerical depth lower bound')
    av = np.isfinite(a) & (a > depth_min)
    bv = np.isfinite(b) & (b > depth_min)
    return {'native_valid':av, 'flip_valid':bv, 'pair_valid':av & bv & original,
            'original_tta_valid':original.copy()}


def disagreements(native, flip_aligned, pair_valid, epsilon=1e-6):
    a,b = np.asarray(native,dtype=np.float64),np.asarray(flip_aligned,dtype=np.float64)
    mask = np.asarray(pair_valid, dtype=bool)
    if a.shape != b.shape or a.shape != mask.shape:
        raise ValueError('Disagreement grids differ')
    if not np.isfinite(epsilon) or epsilon <= 0:
        raise ValueError('Positive epsilon required')
    if np.any(mask & (~np.isfinite(a) | ~np.isfinite(b) | (a <= 0) | (b <= 0))):
        raise ValueError('Pair-valid values must be finite and positive')
    x,y = a[mask],b[mask]
    delta = np.abs(x-y)
    values = (delta/(np.abs(x)+epsilon),delta/(np.abs(x)+np.abs(y)+epsilon),
              np.abs(np.log(x+epsilon)-np.log(y+epsilon)),delta)
    out = {}
    for name,value in zip(DISAGREEMENTS,values):
        if not np.isfinite(value).all():
            raise ValueError('Finite valid depths produced nonfinite disagreement')
        field = np.full(a.shape, np.nan, dtype=np.float64)
        field[mask] = value
        out[name] = field
    return out


def percentile(values, mask):
    values = np.asarray(values,dtype=np.float64)
    mask = np.asarray(mask,dtype=bool)
    if values.shape != mask.shape or np.any(mask & ~np.isfinite(values)):
        raise ValueError('Finite score required everywhere in the declared rank domain')
    out = np.full(values.shape,np.nan,dtype=np.float64)
    if mask.any():
        out[mask] = (rankdata(values[mask],method='average')-.5)/int(mask.sum())
    return out


def build_scores(confidence, disagreement, masks, fusion_weight=.5):
    c,t = np.asarray(confidence,dtype=np.float64),np.asarray(disagreement,dtype=np.float64)
    nv,pv = masks['native_valid'],masks['pair_valid']
    if not (c.shape == t.shape == nv.shape == pv.shape):
        raise ValueError('Risk inputs have different pixel grids')
    if not np.isfinite(fusion_weight) or not 0 <= fusion_weight <= 1:
        raise ValueError('Fusion weight outside [0,1]')
    native_domain = nv & np.isfinite(c)
    flip_domain = pv & np.isfinite(t)
    fused_domain = native_domain & flip_domain
    nr = percentile(-c,native_domain)
    fr = percentile(t,flip_domain)
    rank = np.full(c.shape,np.nan)
    maxrisk = np.full(c.shape,np.nan)
    rank[fused_domain] = fusion_weight*nr[fused_domain] + (1-fusion_weight)*fr[fused_domain]
    maxrisk[fused_domain] = np.maximum(nr[fused_domain],fr[fused_domain])
    aware = nr.copy()
    aware[fused_domain] = rank[fused_domain]
    fields = {'NativeOnly':nr,'FlipOnly':fr,'RankFusion':rank,'MaxFusion':maxrisk,'ValidityAwareFusion':aware}
    domains = {'NativeOnly':native_domain,'FlipOnly':flip_domain,'RankFusion':fused_domain,
               'MaxFusion':fused_domain,'ValidityAwareFusion':native_domain}
    out = {}
    for name,risk in fields.items():
        allowed = domains[name]
        if np.any(allowed & (~np.isfinite(risk) | (risk < 0) | (risk > 1))):
            raise ValueError('Invalid bounded relative risk')
        diagnostic = np.ones(c.shape,dtype=np.float64)
        diagnostic[allowed] = risk[allowed]
        reliability = np.zeros(c.shape,dtype=np.float64)
        reliability[allowed] = 1-risk[allowed]
        out[name] = {'risk':risk,'prior_allowed':allowed.copy(),'policy_diagnostic_risk':diagnostic,
                     'reliability':reliability,'native_fallback':native_domain & ~fused_domain if name=='ValidityAwareFusion' else np.zeros(c.shape,dtype=bool)}
    return out


def prior_terms(cg,bg,eta,disparity,mono_disparity,s,alpha=.01):
    """Float64 transcription of the original positive-disparity prior mask."""
    arrays = [np.asarray(v,dtype=np.float64) for v in (cg,bg,eta,disparity,mono_disparity,s)]
    if len({a.shape for a in arrays}) != 1 or not all(np.isfinite(a).all() for a in arrays):
        raise ValueError('Finite matching native normal-equation grids required')
    cg,bg,eta,d,dm,s = arrays
    if not np.isfinite(alpha) or alpha < 0 or (s<0).any() or (s>1).any() or (eta<0).any():
        raise ValueError('Invalid prior coefficient or native damping')
    m = (dm>0).astype(np.float64)
    return cg+m*s*alpha+(1-m*s)*eta,bg-m*s*alpha*(d-dm)


def geometry_depth_covariance(A,E,cg,eta,lm=1e-4,ep=.1,chunk=256):
    """CPU reference: prior-free damped marginal inverse-normal diagonal.

    Native U/UBA may affect A/E/cg. No mono prediction or reliability is an input.
    The native Schur-then-diagonal-damping order is preserved exactly.
    """
    A,E = np.asarray(A,dtype=np.float64),np.asarray(E,dtype=np.float64)
    cg,eta = np.asarray(cg,dtype=np.float64).ravel(),np.asarray(eta,dtype=np.float64).ravel()
    if A.shape != (E.shape[0],E.shape[0]) or E.shape[1] != len(cg) or cg.shape != eta.shape:
        raise ValueError('Geometry block dimensions differ')
    if not all(np.isfinite(x).all() for x in (A,E,cg,eta)) or (cg+eta<=0).any():
        raise ValueError('Finite positive prior-free depth curvature required')
    if lm<0 or ep<=0 or not np.allclose(A,A.T,rtol=1e-12,atol=1e-12):
        raise ValueError('Symmetric geometry and native positive damping required')
    q=1/(cg+eta)
    h=A-(E*q)@E.T
    hd=h+np.diag(ep+lm*np.diag(h))
    L=np.linalg.cholesky(hd)
    diagonal=q.copy()
    for first in range(0,len(q),chunk):
        last=min(first+chunk,len(q))
        eq=E[:,first:last]*q[first:last]
        z=np.linalg.solve(L,eq)
        diagonal[first:last]+=np.sum(z*z,axis=0)
    return diagonal,hd


def geometry_need(covariance_diagonal, disparity, mask, epsilon=1e-6):
    v,d,m = np.asarray(covariance_diagonal),np.asarray(disparity),np.asarray(mask,dtype=bool)
    if v.shape!=d.shape or d.shape!=m.shape or not m.any() or np.any(m & (~np.isfinite(v) | (v<0) | ~np.isfinite(d))):
        raise ValueError('No admitted finite geometry covariance domain')
    u=float(np.median(np.sqrt(v[m])/(np.abs(d[m])+epsilon)))
    return u/(1+u),u
