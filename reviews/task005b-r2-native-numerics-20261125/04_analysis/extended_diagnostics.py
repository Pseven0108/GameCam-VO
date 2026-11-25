import os,sys,pathlib,json,csv,itertools
os.environ['CUDA_VISIBLE_DEVICES']=''
sys.path.insert(0,r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125\cpu_plot_dependencies')
import numpy as np
from analyze_pairs import ROOT,RECV,compare,FINAL,save_csv
def main():
 plain={p.stem:dict(np.load(p,allow_pickle=False)) for p in (RECV/'plain').glob('*.npz')}
 trace={p.stem:dict(np.load(p,allow_pickle=False)) for p in (RECV/'trace').glob('*.npz')}
 data={**plain,**trace};rows=[];summary=[]
 for tag,a in data.items():
  d=a['disps'];summary.append({'tag':tag,'negative_disparities':int((d<0).sum()),'zero_disparities':int((d==0).sum()),'positive_disparities':int((d>0).sum()),'minimum_disparity':float(d.min()),'maximum_disparity':float(d.max())})
 for left,right in itertools.combinations(data,2):
  a,b=data[left]['disps'],data[right]['disps'];valid=(a>0)&(b>0)
  ad=(1./a[valid].astype('f8')).astype('f4');bd=(1./b[valid].astype('f8')).astype('f4')
  rows.append({'left':left,'right':right,'domain':'positive_disparities_in_both','excluded_pixels':int((~valid).sum()),'formula':'1/disparity; native inverse-depth parameter units; not metric GT depth',**compare(ad,bd)})
 save_csv('DEPTH_RECIPROCAL_COMPARISON.csv',rows);save_csv('RAW_DISPARITY_VALIDITY.csv',summary)
 # Native-system conditioning (R1 paths preserved the exact lower-triangle solve input).
 systems=[]
 for tag in ['paths_1','paths_2']:
  a=plain[tag]
  for it in (1,2):
   raw=a[f'iter{it}_L_damped_raw'];lower=np.tril(raw);H=lower+np.tril(raw,-1).T
   eig=np.linalg.eigvalsh(H);rhs=a[f'iter{it}_rhs'].reshape(-1);dx=a[f'iter{it}_dx'].reshape(-1).astype('f8')
   residual=np.linalg.norm(H@dx-rhs)/(np.linalg.norm(rhs)+1e-300)
   systems.append({'tag':tag,'iteration':it,'dimension':len(eig),'SPD':bool(np.all(eig>0)),'min_eigenvalue':float(eig.min()),'max_eigenvalue':float(eig.max()),'condition_number_2':float(np.max(np.abs(eig))/np.min(np.abs(eig))),'relative_solve_residual':float(residual),'triangle_contract':'Eigen LLT lower self-adjoint; no upper/lower averaging'})
 save_csv('LINEAR_SYSTEM_CONDITIONING.csv',systems)
 rows=list(csv.DictReader((ROOT/'04_analysis/PLAIN_PAIRWISE_ERRORS.csv').open()))
 group={}
 for name,pairs in {'installed_repeat':[('original_1','original_2')],'reference_repeat':[('reference_1','reference_2')],'paths_repeat':[('paths_1','paths_2')],'installed_vs_reference':[(a,b) for a in ['original_1','original_2'] for b in ['reference_1','reference_2']],'installed_vs_paths':[(a,b) for a in ['original_1','original_2'] for b in ['paths_1','paths_2']],'reference_vs_paths':[(a,b) for a in ['paths_1','paths_2'] for b in ['reference_1','reference_2']]}.items():
  selected=[r for r in rows if (r['left'],r['right']) in pairs]
  group[name]={'pair_count':len(pairs),'all_fields_passing_pairs':sum(all(r['PASS']=='True' for r in selected if (r['left'],r['right'])==p) for p in pairs),'max_dx_absolute_difference':max(float(r['max_abs']) for r in selected if r['field']=='dx_last'),'max_dz_absolute_difference':max(float(r['max_abs']) for r in selected if r['field']=='dz_last'),'total_dx_violations':sum(int(r['violations']) for r in selected if r['field']=='dx_last'),'total_dz_violations':sum(int(r['violations']) for r in selected if r['field']=='dz_last')}
 (ROOT/'04_analysis/IMPLEMENTATION_GROUP_SUMMARY.json').write_text(json.dumps(group,indent=2)+'\n')
 print(json.dumps({'implementation_groups':group,'systems':systems},indent=2))
if __name__=='__main__':main()
