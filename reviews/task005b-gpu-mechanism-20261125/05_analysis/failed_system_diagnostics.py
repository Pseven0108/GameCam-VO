"""CPU diagnostics of preserved failed outputs; never execute native replay."""
import pathlib,tarfile,io,json,csv,sys
import numpy as np
from analyze_native import ROOT,RECEIVER,sym_lower,spectrum

def norm(x):return float(np.linalg.norm(np.asarray(x,dtype=np.float64)))

def main():
    path=RECEIVER/'partial_D0_S1_RGB233.tar'
    wanted=['FROZEN_D.npz','NATIVE_UPDATE_D_FAILED_ENDPOINT.npz','NATIVE_UPDATE_D0_ORIGINAL.npz']
    data={}
    with tarfile.open(path,'r:') as archive:
        for member in archive:
            name=member.name.removeprefix('./')
            if name in wanted:
                with np.load(io.BytesIO(archive.extractfile(member).read()),allow_pickle=False) as arrays:
                    data[name]={k:arrays[k] for k in arrays.files}
    results=[]
    for iteration in (1,2):
        prefix='iter%d_'%iteration
        failed=data[wanted[1]];frozen=data[wanted[0]]
        matrix=sym_lower(failed[prefix+'L_damped_raw'].astype(np.float64))
        rhs=failed[prefix+'rhs'].astype(np.float64).ravel()
        dx=failed[prefix+'dx'].astype(np.float64).ravel()
        spec=spectrum(matrix)
        results.append({'internal_iteration':iteration,'pose_system_size':len(rhs),'L_SPD':spec['SPD'],
                        'L_eigenvalue_min':float(np.linalg.eigvalsh(matrix)[0]),
                        'L_eigenvalue_max':float(np.linalg.eigvalsh(matrix)[-1]),'L_condition_2':spec['condition_2'],
                        'native_dx_relative_linear_residual':norm(matrix@dx-rhs)/max(norm(rhs),1e-30),
                        'native_vs_frozen_dx_norm':norm(failed[prefix+'dx']-frozen[prefix+'dx']),
                        'native_vs_frozen_dz_norm':norm(failed[prefix+'dz']-frozen[prefix+'dz']),
                        'native_vs_frozen_U_before_norm':norm(failed[prefix+'U_before']-frozen[prefix+'U_before']),
                        'all_matrix_rhs_dx_finite':bool(np.isfinite(matrix).all() and np.isfinite(rhs).all() and np.isfinite(dx).all())})
    with (ROOT/'05_analysis/FAILED_CONTEXT_LINEAR_DIAGNOSTICS.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(results[0]));writer.writeheader();writer.writerows(results)
    proof={'state':'D0_S1_RGB233','candidate':'NATIVE_UPDATE_D_FAILED_ENDPOINT',
           'GPU_calls':0,'two_native_internal_iterations_preserved':True,'observations':results,
           'installed_reference_has_internal_system_trace':False,
           'scope':'A well-conditioned or low-residual candidate system does not prove equivalence with the installed original. No original-vs-original replay was performed.',
           'cause_established':False}
    (ROOT/'05_analysis/FAILED_CONTEXT_LINEAR_DIAGNOSTICS.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps(proof))

if __name__=='__main__':main()
