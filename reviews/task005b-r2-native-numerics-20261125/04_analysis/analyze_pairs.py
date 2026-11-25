import os,sys,pathlib,json,csv,itertools,hashlib
os.environ['CUDA_VISIBLE_DEVICES']=''
sys.path.insert(0,r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125\cpu_plot_dependencies')
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
RECV=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-R2-20261125-R1')/'expanded/results'
FINAL=['dx_last','dz_last','poses','disps','uncertainties','temp_y_cdot','affine_weights']
ATOL=1e-6;RTOL=1e-5
def compare(a,b):
 assert a.shape==b.shape and a.dtype==b.dtype
 aa=a.astype(np.float64);bb=b.astype(np.float64);delta=np.abs(aa-bb);limit=ATOL+RTOL*np.abs(bb)
 return {'elements':a.size,'bitwise_identical':bool(np.array_equal(np.ascontiguousarray(a).view('u1'),np.ascontiguousarray(b).view('u1'))),'numerically_changed':int(np.count_nonzero(a!=b)),'violations':int(np.count_nonzero(delta>limit)),'max_abs':float(delta.max()) if a.size else 0.,'rms_abs':float(np.sqrt(np.mean(delta**2))) if a.size else 0.,'max_error_to_tolerance':float((delta/limit).max()) if a.size else 0.,'PASS':bool(np.all(delta<=limit))}
def save_csv(name,rows):
 with (ROOT/'04_analysis'/name).open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def analyze(phase):
 source=RECV/phase
 paths=sorted(source.glob('*.npz'));assert len(paths)==(6 if phase=='plain' else 4)
 data={p.stem:dict(np.load(p,allow_pickle=False)) for p in paths}
 names=json.loads((ROOT/'02_candidate/TRACE_SCHEMA.json').read_text())
 all_rows=[];pairs=[];first=[]
 for left,right in itertools.combinations(data,2):
  a,b=data[left],data[right];overall=True;any_diff=False
  keys=FINAL if phase=='plain' else [f'iter{it}_{n}' for it in (1,2) for n in names]+FINAL
  first_numerical=first_violation=None
  for key in keys:
   result=compare(a[key],b[key]);row={'left':left,'right':right,'field':key,**result};all_rows.append(row)
   overall &= result['PASS'];any_diff |= not result['bitwise_identical']
   if result['numerically_changed'] and first_numerical is None:first_numerical=key
   if not result['PASS'] and first_violation is None:first_violation=key
  pair={'left':left,'right':right,'PASS':bool(overall),'bitwise_identical':not any_diff,'first_numerical_difference':first_numerical,'first_tolerance_violation':first_violation}
  pairs.append(pair)
  if phase=='trace':first.append(pair)
 save_csv(phase.upper()+'_PAIRWISE_ERRORS.csv',all_rows)
 (ROOT/'04_analysis'/(phase.upper()+'_PAIRWISE_SUMMARY.json')).write_text(json.dumps({'atol':ATOL,'rtol':RTOL,'pairs':pairs,'passing_pairs':sum(p['PASS'] for p in pairs),'total_pairs':len(pairs)},indent=2)+'\n')
 print(json.dumps({'phase':phase,'pairs':pairs},indent=2))
 if phase=='trace':
  reduced=ROOT/'04_analysis/reduced_traces';reduced.mkdir(exist_ok=True)
  for tag,arrays in data.items():
   keep={k:v for k,v in arrays.items() if k in ('dx_last','affine_weights') or k.endswith(('_J_linear','_affine_du','_affine_after','_affine_before'))}
   np.savez_compressed(reduced/(tag+'.npz'),**keep)
 return data
if __name__=='__main__':analyze(sys.argv[1])
