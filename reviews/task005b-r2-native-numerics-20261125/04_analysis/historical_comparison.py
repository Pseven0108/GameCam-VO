import os,sys,pathlib,json,tarfile,io,itertools
os.environ['CUDA_VISIBLE_DEVICES']=''
sys.path.insert(0,r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125\cpu_plot_dependencies')
import numpy as np
from analyze_pairs import ROOT,RECV,FINAL,compare,save_csv
prior=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-GPU-20261125-R1\partial_D0_S1_RGB233.tar')
with tarfile.open(prior) as archive:
 old={}
 for tag in ['NATIVE_UPDATE_D0_ORIGINAL','NATIVE_UPDATE_D_FAILED_ENDPOINT']:
  member=next(m for m in archive.getmembers() if m.name.endswith('/'+tag+'.npz'))
  with np.load(io.BytesIO(archive.extractfile(member).read()),allow_pickle=False) as a:old[tag]={k:a[k] for k in a.files}
rows=[]
for tag,a in old.items():
 for p in sorted((RECV/'plain').glob('*.npz')):
  b=np.load(p,allow_pickle=False)
  for n in FINAL:
   key=n if tag.endswith('_ORIGINAL') else {'dx_last':'last_dx','dz_last':'last_dz'}.get(n,'final_'+n)
   rows.append({'left':'R1_'+tag,'right':'R2_'+p.stem,'field':n,**compare(a[key],b[n])})
save_csv('HISTORICAL_ENDPOINT_COMPARISON.csv',rows)
print(json.dumps({'rows':len(rows),'historical_inputs_or_outputs_modified':False}))
