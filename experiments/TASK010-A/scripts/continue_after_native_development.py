"""Resume after diagnosed observer/launcher preparation, without rerunning model caches."""
import json
import argparse
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A';PY='D:/aaa/envs/gamecam-vo/python.exe'
p=argparse.ArgumentParser();p.add_argument('--state',default='forkserver_dev_r6_STATE.json');args=p.parse_args()
path=TASK/'private'/args.state;deadline=time.monotonic()+3600
while time.monotonic()<deadline:
    if path.exists():
        state=json.loads(path.read_text())
        if state['status']=='COMPLETE':break
        if state['status']!='STARTED':raise RuntimeError('Native preparation failed; no downstream experiment launched')
    time.sleep(2)
else:raise RuntimeError('Native preparation deadline')
for script in ['evaluate_runs.py','summarize_experiments.py','freeze_transfer.py']:
    subprocess.run([PY,'-u','-B','experiments/TASK010-A/scripts/'+script],cwd=ROOT,check=True)
with (TASK/'private/forkserver_holdout_launcher.log').open('x') as log:
    subprocess.run(['wsl','--exec','sh','/mnt/d/aaa/GameCam-VO-TASK010-A/experiments/TASK010-A/scripts/run_native.sh',
        'experiments/TASK010-A/scripts/native_holdout_controller.py'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
for script in ['evaluate_runs.py','summarize_experiments.py']:
    subprocess.run([PY,'-u','-B','experiments/TASK010-A/scripts/'+script],cwd=ROOT,check=True)
(TASK/'private/CONTINUATION_COMPLETE.json').write_text(json.dumps({'status':'COMPLETE','automatic_retry':False},indent=2))
