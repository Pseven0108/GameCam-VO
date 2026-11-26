"""Pause only the Task008 online resolver before installing its offline cache."""
import json
import os
from pathlib import Path
import signal

W=Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1')
assert json.loads((W/'ENV_RECOVERY_STATE.json').read_text())['stage']=='INSTALL_EXACT_OFFICIAL_WHEELS'
found=[]
for d in Path('/proc').iterdir():
    if not d.name.isdigit():continue
    try:a=(d/'cmdline').read_bytes().split(b'\0');env=(d/'environ').read_bytes()
    except (FileNotFoundError,PermissionError,ProcessLookupError):continue
    if len(a)>5 and a[0]==b'/opt/gamecam-pi3mos/envs/pi3mos-infer/bin/python' and a[1:4]==[b'-m',b'pip',b'install'] and any(x.endswith(b'torch-2.3.1+cu121-cp310-cp310-linux_x86_64.whl') for x in a) and ('TMPDIR='+str(W/'tmp')).encode() in env:
        found.append(int(d.name))
assert len(found)==1,'Do not terminate any unidentified process'
os.kill(found[0],signal.SIGTERM)
r={'stopped_task_owned_pip_PID':found[0],'reason':'Local Linux dependency wheelhouse is faster than measured server download route',
   'original_envs_or_other_processes_touched':False,'GPU_model_runs':0,'partial_downloads_preserved':True}
with (W/'RUNTIME_LIBRARY_TRANSPORT_CHANGE.json').open('x') as f:json.dump(r,f,indent=2)
print(json.dumps(r,indent=2))
