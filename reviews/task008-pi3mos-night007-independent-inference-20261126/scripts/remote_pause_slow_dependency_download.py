"""Stop only this task's identified pip download before switching transport."""
import json
import os
from pathlib import Path
import signal
import time

W=Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1')
state=json.loads((W/'ENV_SETUP_STATE.json').read_text());assert state['stage']=='INSTALL_TORCH_CU121'
matched=[]
for p in Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:argv=(p/'cmdline').read_bytes().split(b'\0');env=(p/'environ').read_bytes()
    except (FileNotFoundError,PermissionError,ProcessLookupError):continue
    if len(argv)>6 and argv[0]==b'/opt/gamecam-pi3mos/envs/pi3mos-infer/bin/python' and argv[1:4]==[b'-m',b'pip',b'install'] and b'torch==2.3.1' in argv and ('TMPDIR='+str(W/'tmp')).encode() in env:
        matched.append(int(p.name))
assert len(matched)==1,'Unexpected matching process count; do not terminate others'
os.kill(matched[0],signal.SIGTERM)
receipt={'stopped_task_owned_pip_PID':matched[0],'reason':'Measured very slow official wheel transport; switch to exact official local wheel transfer',
         'other_processes_touched':False,'GPU_experiments_started':0,'partial_download_preserved':True,'original_environments_touched':False}
with (W/'DEPENDENCY_DOWNLOAD_ROUTE_CHANGE.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2);f.write('\n')
print(json.dumps(receipt,indent=2))
