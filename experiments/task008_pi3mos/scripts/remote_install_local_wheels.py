"""Install exact transferred wheels in the new env; leave original envs alone."""
import json
import os
from pathlib import Path
import subprocess
import textwrap

W=Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1')
assert Path('/opt/gamecam-pi3mos/envs/pi3mos-infer/bin/python').is_file()
state=json.loads((W/'ENV_SETUP_STATE.json').read_text());assert state['INSTALL_TORCH_CU121_exit_code']==-15
assert len(list((W/'wheelhouse').glob('*.whl')))==2
(W/'dependency_constraints.txt').write_text('numpy==1.26.4\n')
script=textwrap.dedent('''
import json,os,pathlib,shutil,subprocess
w=pathlib.Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1')
py='/opt/gamecam-pi3mos/envs/pi3mos-infer/bin/python'
state={'stage':'STARTING_WHEEL_TRANSPORT_RECOVERY','GPU_model_runs':0,'official_Torch_wheels_transferred_and_SHA_verified':True}
def save():(w/'ENV_RECOVERY_STATE.json').write_text(json.dumps(state,indent=2)+'\\n')
def run(args,label):
 state['stage']=label;save()
 env={**os.environ,'CUDA_VISIBLE_DEVICES':'','TMPDIR':str(w/'tmp'),'PYTHONDONTWRITEBYTECODE':'1','PIP_NO_CACHE_DIR':'1'}
 with (w/'logs'/(label+'.log')).open('xb') as f:p=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,env=env,timeout=1800)
 state[label+'_exit_code']=p.returncode;save()
 if p.returncode:raise RuntimeError(label+' failed; keep logs and partial new env')
try:
 wheels=[str(p) for p in sorted((w/'wheelhouse').glob('*.whl'))]
 run([py,'-m','pip','install','--no-cache-dir','--progress-bar','off','--index-url','https://mirrors.aliyun.com/pypi/simple','--constraint',str(w/'dependency_constraints.txt'),*wheels],'INSTALL_EXACT_OFFICIAL_WHEELS')
 run([py,'-m','pip','install','--no-cache-dir','--progress-bar','off','--index-url','https://mirrors.aliyun.com/pypi/simple','numpy==1.26.4','pillow','einops','huggingface_hub==0.26.5','safetensors','plyfile','gdown','opencv-python-headless==4.10.0.84'],'INSTALL_MINIMAL_MODEL_DEPS_RECOVERY')
 with (w/'ENVIRONMENT_PIP_FREEZE.txt').open('xb') as f:subprocess.run([py,'-m','pip','freeze'],stdout=f,check=True)
 state['stage']='INDEPENDENT_ENV_READY';state['free_disk']={p:shutil.disk_usage(p).free for p in ['/','/root/rivermind-data']};save()
except Exception as e:
 state['stage']='ENV_RECOVERY_STOPPED';state['error']=str(e);save();raise
''')
path=W/'install_exact_local_wheels.py';path.write_text(script)
with (W/'logs/ENV_RECOVERY_CONTROLLER.log').open('xb') as out:
    p=subprocess.Popen(['/usr/bin/python3','-u',str(path)],stdout=out,stderr=subprocess.STDOUT,start_new_session=True,
                       env={**os.environ,'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1'})
print(json.dumps({'environment_install_PID':p.pid,'source_or_model_semantics_changed':False,'original_envs_modified':False}))
