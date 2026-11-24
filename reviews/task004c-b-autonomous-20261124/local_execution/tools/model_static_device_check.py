import json
from remote_cpu import ROOT,call
code=r'''
import pathlib,json
r=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/torch_hub/yvanyin_metric3d_main/mono/model')
result={}
for p in r.rglob('*.py'):
 lines=[{'line':i,'code':s.strip()} for i,s in enumerate(p.read_text().splitlines(),1) if '.cuda(' in s or "device='cuda" in s or 'device="cuda' in s]
 if lines:result[str(p.relative_to(r))]=lines
print(json.dumps(result))
'''
d=json.loads(call('MODEL_CPU_DEVICE_STATIC_CHECK',code))
(ROOT/'evidence/MODEL_CPU_DEVICE_STATIC_CHECK.json').write_text(json.dumps(d,indent=2));print(json.dumps(d,indent=2))
