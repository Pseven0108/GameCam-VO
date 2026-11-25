"""Independent FP64 formula checks; sealed input read as bytes, no torch import."""
import importlib.util,itertools
from numerics import *
R2=ROOT.parent/'GAMECAM_TASK005B_R2_NUMERICAL_EQUIVALENCE_20261125_R1'
sys.path.insert(0,str(R2/'04_analysis'))
spec=importlib.util.spec_from_file_location('r2_sealed_feature_reader',R2/'04_analysis/feedback_math.py')
reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
def main():
    first=load('reference_native_01');kx=first['iter1_kx'];features,proof=reader.read_dino(kx);features64=features.astype('f8')
    identity=json.loads((DATA/'INPUT_IDENTITY.json').read_text());s=identity['scalars'];rows=[]
    # Fixed input FP64 J_linear reference, independent of both CUDA atomic schedules.
    old=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-R2-20261125-R1/expanded/results/trace/trace_reference_1.npz')
    with np.load(old,allow_pickle=False) as z:
        total=z['iter1_J_total'].astype('f8');temp=z['iter1_temp_before_linear'][kx].reshape(len(kx),-1).astype('f8')
    dldy=total/(1.+1.1*np.exp(-temp))
    reference=np.concatenate([np.einsum('kp,kcp->kc',dldy,features64,optimize=True),dldy.sum(axis=1)[:,None]],axis=1)/3600.
    np.savez_compressed(OUT/'J_LINEAR_FP64_REFERENCE.npz',reference=reference)
    for i in range(1,17):rows.append({'tag':f'linear_{i:02d}','iteration':0,'quantity':'isolated_J_linear_vs_FP64_reference',**compare(reference.astype('f4'),load(f'linear_{i:02d}')['J_linear'])})
    for group in ['reference_native','paths_native','reference_fixed','paths_fixed']:
        for rep in range(1,5):
            tag=f'{group}_{rep:02d}';a=load(tag)
            for it in (1,2):
                p=f'iter{it}_';J=a[p+'J_linear'];du=a[p+'affine_du'];before=a[p+'affine_before_linear'];after=a[p+'affine_after']
                rec_du=np.float32(-s['lr'])*J.mean(axis=0,dtype=np.float32)
                rec_after=before+(du-np.float32(s['weight_decay'])*before)
                tempref=np.einsum('c,kcp->kp',after[:-1].astype('f8'),features64,optimize=True)+float(after[-1])
                Uref=np.log(1.1+np.exp(tempref))
                quantities=[('affine_du_from_J_linear',rec_du,du),('affine_after_from_native_du',rec_after,after),('temp_from_affine_FP64',tempref.astype('f4'),a[p+'temp_after'][kx].reshape(len(kx),-1)),('U_computed_from_affine_FP64',Uref.astype('f4'),a[p+'U_computed'][kx].reshape(len(kx),-1))]
                for name,pred,actual in quantities:rows.append({'tag':tag,'iteration':it,'quantity':name,**compare(pred,actual)})
    save_csv('INDEPENDENT_FEEDBACK_FORMULA_CHECKS.csv',rows)
    save_json('INDEPENDENT_FEEDBACK_FORMULA_AUDIT.json',{'feature_provenance':proof,'checks':len(rows),'all_original_tolerance_PASS':all(r['PASS'] for r in rows),'failed_rows':[r for r in rows if not r['PASS']],'torch_imported':False,'FP64_reference_is_not_exact_native_atomic_order':True})
    print(json.dumps({'checks':len(rows),'PASS':sum(r['PASS'] for r in rows),'feature_bytes':proof['selected_feature_bytes']},indent=2))
if __name__=='__main__':main()
