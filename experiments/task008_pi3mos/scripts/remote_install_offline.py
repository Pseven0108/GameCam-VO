"""Offline installation in the task-specific system-disk environment."""
import json
import os
from pathlib import Path
import subprocess
import textwrap

W=Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1')
assert json.loads((W/'ENV_RECOVERY_STATE.json').read_text())['stage']=='ENV_RECOVERY_STOPPED'
assert len(list((W/'wheelhouse').glob('*.whl')))>40
assert not (W/'ENV_OFFLINE_STATE.json').exists()
script=textwrap.dedent('''
import json,os,pathlib,shutil,subprocess,time
w=pathlib.Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1')
py='/opt/gamecam-pi3mos/envs/pi3mos-infer/bin/python'
s={'stage':'INSTALLING_OFFLINE','GPU_model_runs':0,'network_download_during_install':False,'original_environments_modified':False}
def save():(w/'ENV_OFFLINE_STATE.json').write_text(json.dumps(s,indent=2)+'\\n')
save()
try:
 env={**os.environ,'CUDA_VISIBLE_DEVICES':'','TMPDIR':str(w/'tmp'),'PYTHONDONTWRITEBYTECODE':'1','PIP_NO_CACHE_DIR':'1'}
 args=[py,'-m','pip','install','--no-index','--find-links',str(w/'wheelhouse'),'--constraint',str(w/'dependency_constraints.txt'),
       '--no-compile','--only-binary=:all:','torch==2.3.1','torchvision==0.18.1','numpy==1.26.4','pillow','einops',
       'huggingface_hub==0.26.5','safetensors','plyfile','gdown==5.2.0','opencv-python-headless==4.10.0.84']
 t=time.monotonic()
 with (w/'logs/INSTALL_OFFLINE.log').open('xb') as f:r=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,env=env,timeout=1200)
 s['pip_exit_code']=r.returncode;s['install_seconds']=time.monotonic()-t;save()
 if r.returncode:raise RuntimeError('Offline dependency installation failed; no inference attempted')
 with (w/'ENVIRONMENT_PIP_FREEZE.txt').open('xb') as f:subprocess.run([py,'-m','pip','freeze'],stdout=f,env=env,check=True)
 with (w/'ENVIRONMENT_PIP_CHECK.txt').open('xb') as f:r=subprocess.run([py,'-m','pip','check'],stdout=f,stderr=subprocess.STDOUT,env=env)
 if r.returncode:raise RuntimeError('pip check failed')
 s['stage']='INDEPENDENT_ENV_READY';s['pip_check_exit_code']=r.returncode
 s['free_disk']={p:shutil.disk_usage(p).free for p in ['/','/root/rivermind-data']};save()
except Exception as e:
 s['stage']='OFFLINE_INSTALL_STOPPED';s['error']=str(e);save();raise
''')
p=W/'install_offline.py';p.write_text(script)
with (W/'logs/ENV_OFFLINE_CONTROLLER.log').open('xb') as f:
    child=subprocess.Popen(['/usr/bin/python3','-B','-u',str(p)],stdout=f,stderr=subprocess.STDOUT,start_new_session=True,
                           env={**os.environ,'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1'})
print(json.dumps({'PID':child.pid,'stage':'OFFLINE_INSTALL_STARTED','original_environments_modified':False}))
