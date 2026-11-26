"""Single serial A/B launch after independent environment and CPU contracts pass."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import textwrap

w=Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R2_FORMAT_VERIFIED')
assert json.loads((w/'ENV_OFFLINE_STATE.json').read_text())['stage']=='INDEPENDENT_ENV_READY'
assert json.loads((w/'CPU_PREPROCESS_CONTRACT.json').read_text())['independent_vs_official_RGB_reader_bitwise_equal']
assert not (w/'INFERENCE_STATE.json').exists()
for row in json.loads((w/'ADAPTER_RELEASE_RECEIPT.json').read_text())['files']:
    p=w/row['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
ck=Path('/root/rivermind-data/external_models/pi3mos_task008_weights/pi3mos_official.pth')
assert ck.stat().st_size==4100235800
h=hashlib.sha256()
with ck.open('rb') as f:
    for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
assert h.hexdigest()=='1a536b1bb6e9c6c16a77b7ed544649351d387e281a16f3d946e0786cdcf23ded'
apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True)
assert not apps.strip(),'Do not compete with another GPU compute process'
script=textwrap.dedent('''
import json,os,pathlib,subprocess,time
w=pathlib.Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R2_FORMAT_VERIFIED')
py='/opt/gamecam-pi3mos/envs/pi3mos-infer/bin/python'
env={**os.environ,'CUDA_VISIBLE_DEVICES':'0','PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(w/'tmp'),
     'HF_HOME':str(w/'hub_cache'),'TORCH_HOME':str(w/'torch_cache')}
args=[py,'-B','-u',str(w/'scripts/infer_pi3mos.py'),'--config',str(w/'configs/night007.json'),
      '--checkpoint','/root/rivermind-data/external_models/pi3mos_task008_weights/pi3mos_official.pth']
start=time.monotonic()
with (w/'logs/INFERENCE.log').open('xb') as f:
 p=subprocess.Popen(args,stdout=f,stderr=subprocess.STDOUT,env=env)
 (w/'INFERENCE_LAUNCH_RECEIPT.json').write_text(json.dumps({'PID':p.pid,'arguments':args,
    'CUDA_VISIBLE_DEVICES':'0','start_UTC':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'retry':False},indent=2)+'\\n')
 code=p.wait()
(w/'INFERENCE_EXIT_RECEIPT.json').write_text(json.dumps({'exit_code':code,'wall_seconds':time.monotonic()-start,
    'auto_retry':False,'end_UTC':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())},indent=2)+'\\n')
''')
p=w/'inference_controller.py';p.write_text(script)
with (w/'logs/INFERENCE_CONTROLLER.log').open('xb') as f:
    child=subprocess.Popen(['/usr/bin/python3','-B','-u',str(p)],stdout=f,stderr=subprocess.STDOUT,
                           start_new_session=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
print(json.dumps({'controller_PID':child.pid,'launch_once':True,'weights_SHA256_verified':h.hexdigest(),'serial_A_then_B':True}))
