import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import json,pathlib,sys,collections
OLD=pathlib.Path(r'D:\aaa\GameCam-VO\experiments\DROID_W_TASK004C_B_IO_COMPAT_20261124_R1')
sys.path.insert(0,str(OLD/'tools'))
from evidence_locations import stage_dir
for arm in ('B1','B2','B4','B3'):
 b=stage_dir(arm);counts=collections.Counter();examples={}
 with (b/'observer.jsonl').open(encoding='utf-8') as f:
  for line in f:
   x=json.loads(line);k=x['type'];counts[k]+=1
   if k not in examples:examples[k]=x
 print('ARM',arm,'EVENT_COUNTS',dict(counts))
 if arm=='B1':
  for k in ('ba_before','ba_after_native','ba_after_clamp','keyframe_decision','frontend_distance','tracking_start','tracking_end','final_ba_start','final_ba_end'):
   if k not in examples:continue
   x=examples[k];print('EVENT',k,'KEYS',list(x))
   print('SCALARS',{kk:v for kk,v in x.items() if not isinstance(v,(dict,list))})
   for kk in ('rows','eta_sample','geometry','positive_depth','prior_support'):
    v=x.get(kk)
    if v is not None:print('DETAIL',kk,json.dumps(v[:1] if isinstance(v,list) else v)[:5500])
  with (b/'schedule.jsonl').open(encoding='utf-8') as f:
   next(f);x=json.loads(next(f))
   print('SCHED',list(x),'kind',x.get('kind'),'rgb',x.get('rgb'),'context',list(x.get('context',{})),'payload_keys',list(x.get('payload',{})))
 print('NATIVE_FILES',[(str(p.relative_to(b)),p.stat().st_size) for p in (b/'native').rglob('*') if p.is_file() and p.suffix not in ('.rrd','.npz')][:20])
