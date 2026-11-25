"""CPU reference for a *fixed linearization*, not a replacement for native BA."""
import numpy as np

CELLS={'A':(1,1),'B':(1,0),'C':(0,1),'D':(0,0)}

def regularization(c_geom,w_geom,disp,prior,eta,alpha,curvature,gradient):
    if curvature not in (0,1) or gradient not in (0,1):
        raise ValueError('Path switches must be binary')
    arrays=[np.asarray(x,dtype=np.float64) for x in (c_geom,w_geom,disp,prior,eta)]
    if len({x.shape for x in arrays})!=1 or any(not np.isfinite(x).all() for x in arrays):
        raise ValueError('All depth arrays must have equal shape and finite values')
    cg,wg,d,dm,e=arrays
    if not np.isfinite(alpha) or alpha<0 or np.any(e<0):raise ValueError('Invalid regularizer')
    m=(dm>0).astype(float);mc=curvature*m;mg=gradient*m
    C=cg+mc*alpha+(1-mc)*e
    p=m*alpha*(d-dm)
    w=wg-mg*alpha*(d-dm)
    if np.any(C<=0):raise ValueError('Depth block not strictly positive')
    return C,w,p

def solve(A,E,v,cg,wg,d,dm,eta,alpha,c,g,lm=1e-4,ep=.1):
    A,E,v=[np.asarray(x,dtype=float) for x in (A,E,v)]
    C,w,p=regularization(cg,wg,d,dm,eta,alpha,c,g)
    q=1/C
    H=A-(E*q)@E.T
    rhs=v-E@(q*w)
    # Native SparseBlock applies damping to the *Schur* diagonal, not to A.
    L=H+np.diag(ep+lm*np.diag(H))
    x=np.linalg.solve(L,rhs)
    z=q*(w-E.T@x)
    return {'C':C,'w':w,'p':p,'Q':q,'H':H,'L':L,'rhs':rhs,'dx':x,'dz':z}

def contrasts(values):
    a,b,c,d=[np.asarray(values[k],dtype=float) for k in 'ABCD']
    return {'curvature_at_g0':b-d,'curvature_at_g1':a-c,
            'gradient_at_c0':c-d,'gradient_at_c1':a-b,
            'interaction':a-b-c+d,'total_on_minus_off':a-d,
            'curvature_average':.5*(b-d+a-c),'gradient_average':.5*(c-d+a-b)}

def spectrum(native_matrix):
    """Diagnose the lower-triangle self-adjoint matrix used by Eigen LLT."""
    M=np.asarray(native_matrix,dtype=np.float64)
    if M.ndim!=2 or M.shape[0]!=M.shape[1] or not np.isfinite(M).all():raise ValueError('Invalid matrix')
    effective=np.tril(M)+np.tril(M,-1).T
    eig=np.linalg.eigvalsh(effective);sv=np.linalg.svd(effective,compute_uv=False)
    tol=np.finfo(float).eps*len(M)*(sv[0] if len(sv) else 0)
    rank=int((sv>tol).sum())
    return {'eigenvalues':eig,'singular_values':sv,'rank':rank,'rank_tolerance':tol,
            'kappa2':float(sv[0]/sv[-1]) if rank==len(M) and sv[-1]>0 else None,
            'SPD':bool(eig[0]>tol),'asymmetry_fro':float(np.linalg.norm(M-M.T)),
            'effective_matrix':effective}
