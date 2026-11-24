import pathlib,json,zipfile,numpy as np
old=pathlib.Path(r'D:\aaa\GameCam-VO\experiments\DROID_W_TASK004C_B_IO_COMPAT_20261124_R1')
roots={'B1':old/'raw_evidence/R3_OFFLINE/attempts/B1','B2':old/'raw_evidence/R3_OFFLINE/attempts/B2','B4':pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125\raw_evidence\R3_OFFLINE\attempts\B4'),'B3':pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125\raw_evidence\R3_OFFLINE\attempts\B3')}
for arm,b in roots.items():
 with zipfile.ZipFile(b/'native/video.npz') as z:
  print('VIDEO',arm,[(i.filename,i.file_size) for i in z.infolist()])
 with (b/'observer.jsonl').open() as f:
  types=set()
  for line in f:
   x=json.loads(line);t=x['type']
   if t in ('stage_boundary','frontend_distance','keyframe_decision') and t not in types:
    types.add(t);y={k:v for k,v in x.items() if k!='rows'};y['rows_count']=len(x.get('rows',[]));print('EVENT',arm,t,json.dumps(y)[:1800])
 with (b/'native_trace.jsonl').open() as f:
  kinds={};first=[]
  for line in f:
   x=json.loads(line);k=x['kind'];kinds[k]=kinds.get(k,0)+1
   if k not in [r['kind'] for r in first]:first.append(x)
 print('TRACE_COUNTS',arm,kinds)
 if arm=='B1':
  for x in first:print('TRACE_KIND_EXAMPLE',x['kind'],str(x)[:500])
