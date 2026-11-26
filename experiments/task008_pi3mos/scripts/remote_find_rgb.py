"""Bounded directory discovery without traversing historical result payloads."""
import json
from pathlib import Path
ROOT=Path('/root/rivermind-data')
out=[]
for d in ['DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1','VIPER_MATCHED_DUAL_BASELINE_R2','DROID_W_TASK003_VAL007_OBSERVATION_R1']:
    p=ROOT/d
    for sub in ['inputs','runtime_cache','staging','source','incoming']:
        base=p/sub
        if not base.is_dir():continue
        for q in [base,*[x for x in base.iterdir() if x.is_dir()]]:
            entries=list(q.iterdir())
            row={'path':str(q),'count':len(entries),'names':[x.name for x in entries[:16]]}
            out.append(row)
            for x in entries:
                if x.is_dir() and ('007' in x.name or 'rgb' in x.name.lower() or x.name in ['images','DROID-W','DROIDW']):
                    a=list(x.iterdir());out.append({'path':str(x),'count':len(a),'names':[v.name for v in a[:16]]})
print(json.dumps(out,indent=2))
