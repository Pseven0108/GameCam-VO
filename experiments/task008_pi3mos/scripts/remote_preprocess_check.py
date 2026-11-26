import json
import os
from pathlib import Path
import subprocess

w=Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1')
assert json.loads((w/'ENV_OFFLINE_STATE.json').read_text())['stage']=='INDEPENDENT_ENV_READY'
py='/opt/gamecam-pi3mos/envs/pi3mos-infer/bin/python'
args=[py,'-B','-u',str(w/'scripts/inspect_model_interface.py'),'--config',str(w/'configs/night007.json')]
r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180,
                 env={**os.environ,'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1'})
with (w/'logs/CPU_PREPROCESS_CHECK.stdout.txt').open('xb') as f:f.write(r.stdout)
with (w/'logs/CPU_PREPROCESS_CHECK.stderr.txt').open('xb') as f:f.write(r.stderr)
print(r.stdout.decode(errors='replace'));print(r.stderr.decode(errors='replace'))
assert r.returncode==0,'CPU preprocessing contract did not pass; no model startup authorized by this launcher'
record=json.loads((w/'CPU_PREPROCESS_CONTRACT.json').read_text())
assert record['independent_vs_official_RGB_reader_bitwise_equal'] and not record['GPU_initialized']
assert record['torch']=='2.3.1+cu121' and record['CUDA_build']=='12.1'
