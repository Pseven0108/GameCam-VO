import json,pathlib
from remote_cpu import ROOT,call
code=r'''
import json,pathlib,hashlib
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_AUTONOMOUS_20261124_R1')
s=r/'source_candidate'
names=['src/slam.py','src/depth_video.py','src/tracker.py','src/motion_filter.py','src/frontend.py','src/backend.py','src/factor_graph.py','src/trajectory_filler.py','src/droid_net.py','native_control/binding.py','native_control/install.py','native_control/dataset.py','native_control/file_backed.py','runner/run_native_smoke.py','configs/identity_lock.json','configs/r2_sealed_config.yaml']
out={}
for n in names:
 p=s/n
 if not p.is_file():p=r/n
 out[n]={'text':p.read_text() if p.is_file() else None,'sha256':hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None}
print(json.dumps(out))
'''
d=json.loads(call('FETCH_OWNING_SOURCES',code))
for n,v in d.items():
 p=ROOT/'source_intake'/n;p.parent.mkdir(parents=True,exist_ok=True)
 if v['text'] is not None:p.write_text(v['text'],encoding='utf-8')
print(json.dumps({k:{'sha256':v['sha256'],'present':v['text'] is not None} for k,v in d.items()},indent=2))
