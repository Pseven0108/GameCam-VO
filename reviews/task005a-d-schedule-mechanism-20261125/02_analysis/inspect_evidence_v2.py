import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import csv,json,pathlib,sys,collections
import numpy as np
OLD=pathlib.Path(r'D:\aaa\GameCam-VO\experiments\DROID_W_TASK004C_B_IO_COMPAT_20261124_R1')
sys.path.insert(0,str(OLD/'tools'))
from evidence_locations import stage_dir
for arm in ('B1','B2','B4','B3'):
 b=stage_dir(arm)
 print('ARM',arm,str(b))
 for name in ('FRONTEND_KEYFRAMES.npz','FINAL_BA_KEYFRAMES.npz'):
  with np.load(b/name,allow_pickle=False) as z:print('NPZ',name,[(k,z[k].shape,str(z[k].dtype)) for k in z.files])
 counts=collections.Counter();examples={}
 with (b/'observer.jsonl').open(encoding='utf-8') as f:
  for line in f:
   x=json.loads(line);k=(x.get('event'),x.get('type'));counts[str(k)]+=1
   if k not in examples:examples[k]=x
 print('OBS_COUNTS',dict(counts))
 if arm=='B1':
  for k,x in examples.items():
   print('OBS_SCHEMA',k,'keys',list(x))
   for kk in ('geometry','disparity','uncertainty','full_disparity_grid','poses','depth','mono_disparity','pose_snapshots','pair_metrics'):
    if kk in x:
     v=x[kk];print('FIELD',kk,json.dumps(v)[:6000])
  with (b/'schedule.jsonl').open(encoding='utf-8') as f:
   for j,line in enumerate(f):
    x=json.loads(line)
    if j==0:continue
    print('SCHED_KEYS',list(x),'kind',x.get('kind'),'rgb',x.get('rgb'),'payload',x.get('payload'),'context_keys',list(x.get('context',{})))
    print('SCHED_GRAPH_KEYS',[list(g) for g in x.get('context',{}).get('graphs',[])])
    break
 print('NATIVE_CONTENTS',[(p.name,p.stat().st_size) for p in (b/'native').glob('*')])
