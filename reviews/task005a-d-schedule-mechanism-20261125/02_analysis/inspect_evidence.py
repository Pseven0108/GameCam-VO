import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import csv,json,pathlib,sys
import numpy as np
OLD=pathlib.Path(r'D:\aaa\GameCam-VO\experiments\DROID_W_TASK004C_B_IO_COMPAT_20261124_R1')
RECEIVER=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125')
print('RUNTIME',sys.executable,'NUMPY',np.__version__)
for n in ('KEYFRAME_STAGE_SCORES.csv','PER_FRAME_ERRORS.csv','FIXED_ENDPOINT_AND_DIRECT_KEYFRAME.csv','RPE_OFFSETS.csv','DESCRIPTIVE_D_S_CONTRASTS.csv'):
    with (OLD/'evaluation'/n).open(encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    print('CSV',n,'rows',len(rows),'columns',list(rows[0]) if rows else [])
    if n=='KEYFRAME_STAGE_SCORES.csv':print(json.dumps(rows))
for arm in ('B1','B2','B4','B3'):
    base=OLD/'raw_evidence/R3_OFFLINE/attempts'/arm
    for n in ('FRONTEND_KEYFRAMES.npz','FINAL_BA_KEYFRAMES.npz'):
        with np.load(base/n,allow_pickle=False) as z:print('NPZ',arm,n,[(k,z[k].shape,str(z[k].dtype)) for k in z.files])
    with (base/'observer.jsonl').open(encoding='utf-8') as f:
        observed=[]
        for line in f:
            x=json.loads(line)
            typ=x.get('event',x.get('type',x.get('stage')))
            if typ not in observed:
                observed.append(typ);print('OBSERVER_SCHEMA',arm,typ,json.dumps(x,ensure_ascii=False)[:5200])
            if len(observed)>=5:break
    with (base/'native_trace.jsonl').open(encoding='utf-8') as f:
        for _ in range(3):
            line=f.readline()
            if line:print('NATIVE_SCHEMA',arm,line[:2200])
    with (base/'schedule.jsonl').open(encoding='utf-8') as f:
        for _ in range(2):print('SCHEDULE_SCHEMA',arm,f.readline()[:2000])
    print('OTHER',arm,[str(p.relative_to(RECEIVER)) for p in (RECEIVER/'raw_evidence/R3_OFFLINE/attempts'/arm).glob('*') if p.is_file()][:25])
