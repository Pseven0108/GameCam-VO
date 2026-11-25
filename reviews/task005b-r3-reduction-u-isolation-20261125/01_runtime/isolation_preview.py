"""CPU read-only descriptive preview after isolated calls; does not run a kernel."""
import pathlib,json,itertools,numpy as np
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_R3_REDUCTION_U_ISOLATION_20261125_R1/results');rows=[]
for kind,fields in [('jjj',['Jii_data','Jjj_data','kf_count']),('linear',['J_linear'])]:
 files=[r/f'{kind}_{i:02d}.npz' for i in range(1,17)]
 assert all(p.exists() for p in files),'Isolated block not finished'
 for field in fields:
  a=[]
  for p in files:
   with np.load(p,allow_pickle=False) as z:a.append(z[field])
  maximum=0.;equal=0;passed=0
  for x,y in itertools.combinations(a,2):
   d=np.abs(x.astype('f8')-y.astype('f8'));maximum=max(maximum,float(d.max()));equal+=np.array_equal(x,y);passed+=bool(np.all(d<=1e-6+1e-5*np.abs(x.astype('f8'))))
  rows.append({'kind':kind,'field':field,'calls':16,'pairs':120,'bitwise_equal_pairs':equal,'original_tolerance_PASS_pairs':passed,'maximum_abs_difference':maximum,'variable_elements':int(np.count_nonzero(np.ptp(np.stack(a).astype('f8'),axis=0)))})
print(json.dumps({'isolated_preview':rows,'not_additional_GPU_execution':True},indent=2))
