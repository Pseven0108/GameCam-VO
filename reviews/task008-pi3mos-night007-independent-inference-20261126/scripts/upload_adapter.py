"""Publish only this task's own reviewed adapter/config to its remote work dir."""
import hashlib
import json
from pathlib import Path

from remote_transport import ROOT,run

names=['scripts/preprocess.py','scripts/visualize_masks.py','scripts/infer_pi3mos.py','scripts/inspect_model_interface.py',
       'scripts/summarize_and_visualize.py','configs/night007.json','configs/rgb_only_roi_plan.json']
rows=[]
for name in names:
    b=(ROOT/name).read_bytes();rows.append({'path':name,'content':b.decode('utf-8'),'sha256':hashlib.sha256(b).hexdigest()})
script='''import hashlib,json,pathlib
w=pathlib.Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1')
rows=json.loads(DATA)
for r in rows:
 p=w/r['path'];assert p.resolve().is_relative_to(w.resolve());p.parent.mkdir(parents=True,exist_ok=True)
 b=r['content'].encode('utf-8');assert hashlib.sha256(b).hexdigest()==r['sha256']
 with p.open('xb') as f:f.write(b)
receipt={'files':[{'path':r['path'],'sha256':r['sha256']} for r in rows],'all_match':True,'official_model_modified':False}
with (w/'ADAPTER_RELEASE_RECEIPT.json').open('x') as f:json.dump(receipt,f,indent=2)
print(json.dumps(receipt,indent=2))
'''.replace('DATA',repr(json.dumps(rows)))
print(run(script,'ADAPTER_RELEASE',timeout=120))
