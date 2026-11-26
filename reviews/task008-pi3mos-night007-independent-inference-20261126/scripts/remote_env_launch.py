"""Continue isolated environment setup after verified source acquisition."""
import json
import os
from pathlib import Path
import subprocess
import textwrap

W=Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1')
source=json.loads((W/'SOURCE_ACQUISITION_VERIFIED.json').read_text())
assert source['source_HEAD']=='1b81d729c4259a5a775eb4aae41f959eea38ae14'
assert not Path('/opt/gamecam-pi3mos/envs/pi3mos-infer').exists()
script=textwrap.dedent('''
import json,os,pathlib,shutil,subprocess
w=pathlib.Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1')
p='/opt/gamecam-pi3mos/envs/pi3mos-infer'
state={'stage':'STARTING_INDEPENDENT_ENV','GPU_model_runs':0}
def save():(w/'ENV_SETUP_STATE.json').write_text(json.dumps(state,indent=2)+'\\n')
def run(argv,label,timeout):
 state['stage']=label;save()
 env={**os.environ,'CUDA_VISIBLE_DEVICES':'','TMPDIR':str(w/'tmp'),'PIP_NO_CACHE_DIR':'1','PYTHONDONTWRITEBYTECODE':'1'}
 with (w/'logs'/(label+'.log')).open('xb') as f:r=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,timeout=timeout,env=env)
 state[label+'_exit_code']=r.returncode;save()
 if r.returncode:raise RuntimeError(label+' failed; retain the partial environment and logs')
try:
 run(['/opt/conda/bin/conda','create','--prefix',p,'--override-channels','-c','conda-forge','python=3.10','pip','-y'],'CREATE_INDEPENDENT_ENV',900)
 run([p+'/bin/python','-m','pip','install','--no-cache-dir','--index-url','https://download.pytorch.org/whl/cu121','torch==2.3.1','torchvision==0.18.1'],'INSTALL_TORCH_CU121',1800)
 run([p+'/bin/python','-m','pip','install','--no-cache-dir','numpy==1.26.4','pillow','einops','huggingface_hub==0.26.5','safetensors','plyfile','gdown','opencv-python-headless==4.10.0.84'],'INSTALL_MINIMAL_MODEL_DEPS',900)
 state['stage']='INDEPENDENT_ENV_READY';state['free_disk']={x:shutil.disk_usage(x).free for x in ['/','/root/rivermind-data']};save()
except Exception as e:
 state['stage']='ENV_SETUP_STOPPED';state['error']=str(e);save();raise
''')
path=W/'create_independent_env.py';path.write_text(script)
with (W/'logs/ENV_SETUP_CONTROLLER.log').open('xb') as out:
    p=subprocess.Popen(['/usr/bin/python3','-u',str(path)],stdout=out,stderr=subprocess.STDOUT,start_new_session=True,
                       env={**os.environ,'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1'})
print(json.dumps({'environment_setup_PID':p.pid,'original_clone_timeout_record_preserved':True,'source_verified':True,'model_runs':0}))
