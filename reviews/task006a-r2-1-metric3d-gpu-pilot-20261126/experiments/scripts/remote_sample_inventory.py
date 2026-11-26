import json,pathlib,hashlib
base=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408')
out={}
for name in ['val_001','val_007','val_010','val_016','val_030']:
 p=base/'data'/name
 out[str(p)]=[]
 if p.exists():
  out[str(p)]=[{'name':x.name,'dir':x.is_dir(),'bytes':x.stat().st_size} for x in sorted(p.iterdir())[:12]]
  for q in sorted(p.iterdir()):
   if q.is_dir():out[str(q)]=[x.name for x in sorted(q.iterdir())[:4]]
p=pathlib.Path('/root/rivermind-data/VIPER_MATCHED_DUAL_BASELINE_R2/manifests')
if p.is_dir():out[str(p)]=[x.name for x in sorted(p.iterdir())[:12]]
print(json.dumps(out,indent=2))
