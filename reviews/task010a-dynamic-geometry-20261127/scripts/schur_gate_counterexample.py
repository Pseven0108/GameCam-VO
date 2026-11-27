"""Float64 algebra check, explicitly synthetic and not a replay of native BA."""
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'


def solve(g,prior,ep,lm):
    A=np.array([[5.,1.],[1.,4.]],np.float64)
    E=np.array([[.7,.2,-.3],[.1,-.4,.5]],np.float64)
    Cg=np.array([3.,4.,2.]);bp=np.array([1.,.4]);bg=np.array([.2,.3,-.5])
    C=g*Cg+prior;Q=1/C
    H=g*A-(g*E*Q)@(g*E).T
    damp=np.diag(ep+lm*np.diag(H));Hd=H+damp
    b=g*bp-(g*E*Q)@(g*bg)
    dx=np.linalg.solve(Hd,b);dz=Q*(g*bg-(g*E).T@dx)
    full=np.block([[g*A+damp,g*E],[(g*E).T,np.diag(C)]])
    direct=np.linalg.solve(full,np.r_[g*bp,g*bg])
    np.testing.assert_allclose(np.r_[dx,dz],direct,rtol=1e-13,atol=1e-13)
    return {'dx':dx.tolist(),'dz':dz.tolist(),'Schur_eigenvalues':np.linalg.eigvalsh(Hd).tolist(),
        'block_vs_Schur_max_abs':float(np.max(abs(np.r_[dx,dz]-direct)))}


def main():
    a=solve(1.,.5,.1,1e-4);b=solve(.94,.5,.1,1e-4)
    pure1=solve(1.,0.,0.,1e-4);pure2=solve(.94,0.,0.,1e-4)
    np.testing.assert_allclose(pure1['dx'],pure2['dx'],rtol=1e-13,atol=1e-13)
    np.testing.assert_allclose(pure1['dz'],pure2['dz'],rtol=1e-13,atol=1e-13)
    result={'status':'PASS','dtype':'float64','evidence_level':'SYNTHETIC_ALGEBRA_ONLY_NOT_HISTORICAL_BA_REPLAY',
        'prior_and_absolute_damping_fixed':{'g1':a,'g094':b,'dx_difference_L2':float(np.linalg.norm(np.array(a['dx'])-b['dx']))},
        'no_prior_no_absolute_damping':{'g1':pure1,'g094':pure2,'uniform_gate_invariance_verified':True},
        'real_DROIDW_curvatures_or_residuals_used':False,'trajectory_root_cause_proven':False}
    (TASK/'01_failure_diagnosis/SCHUR_GATE_FLOAT64_CHECK.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
