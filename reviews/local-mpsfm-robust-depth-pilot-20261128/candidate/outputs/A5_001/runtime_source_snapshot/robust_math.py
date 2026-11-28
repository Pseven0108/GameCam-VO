"""Float64 CPU oracle for the native-disparity Cauchy IRLS transfer."""
import numpy as np

def terms(Cg,bg,eta,dm,d,a,alpha=.01,relative_scale=.1):
    Cg,bg,eta,dm,d,a=np.broadcast_arrays(*[np.asarray(x,dtype=np.float64) for x in [Cg,bg,eta,dm,d,a]])
    if not all(np.isfinite(x).all() for x in [Cg,bg,eta,dm,d,a]):raise ValueError('Nonfinite input')
    if np.any((a<0)|(a>1)) or np.any(eta<0):raise ValueError('Invalid coefficient/damping')
    if not np.isfinite(relative_scale) or relative_scale<=0 or alpha<0:raise ValueError('Invalid scale')
    m=(dm>0).astype(np.float64);r=d-dm;tau=np.maximum(relative_scale*np.abs(dm),1e-6)
    q=1/(1+(r/tau)**2);ma=m*a
    objective=.5*ma*alpha*tau**2*np.log1p((r/tau)**2)
    return dict(C=Cg+ma*alpha*q+(1-ma)*eta,b=bg-ma*alpha*q*r,q=q,objective=objective,
        gradient=ma*alpha*q*r,damping=(1-ma)*eta,prior_curvature=ma*alpha*q)

def quadratic(Cg,bg,eta,dm,d,a,alpha=.01):
    m=np.asarray(dm)>0;ma=m*np.asarray(a)
    return np.asarray(Cg)+ma*alpha+(1-ma)*np.asarray(eta),np.asarray(bg)-ma*alpha*(np.asarray(d)-dm)

def surrogate(value,at,dm,a=1.,alpha=.01,scale=.1):
    tau=max(scale*abs(dm),1e-6);r0=at-dm;q=1/(1+(r0/tau)**2)
    base=.5*a*alpha*tau**2*np.log1p((r0/tau)**2)
    return base+.5*a*alpha*q*((value-dm)**2-r0**2)
