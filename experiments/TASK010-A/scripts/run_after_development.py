"""Current-task continuation only, no GPU overlap, no retry or external scheduler."""
import json
from pathlib import Path
import subprocess
import time
import sys

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
deadline=time.monotonic()+4*3600
while time.monotonic()<deadline:
    state=json.loads((TASK/'private/development_plan_STATE.json').read_text())
    if state['status']=='COMPLETE':break
    if state['status']!='STARTED':raise RuntimeError('Development stopped; Full-model smoke must not start automatically')
    time.sleep(2)
else:raise RuntimeError('Development wait limit reached; no GPU work launched')
print('DEVELOPMENT_COMPLETE_STARTING_FULL_MODEL_SMOKE',flush=True)
raise SystemExit(subprocess.run(['D:/aaa/envs/gamecam-vo/python.exe','-u','-B',
    'experiments/TASK010-A/scripts/run_jobs.py','--plan','experiments/TASK010-A/private/full_geo_smoke_plan.json'],cwd=ROOT).returncode)
