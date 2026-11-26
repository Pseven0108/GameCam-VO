"""Create only Task008-owned paths; clone source and create an isolated env."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import textwrap

WORK=Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1')
REPO=Path('/root/rivermind-data/external_models/Pi3MOS-SLAM_1b81d729c4259a5a775eb4aae41f959eea38ae14')
ENV=Path('/opt/gamecam-pi3mos/envs/pi3mos-infer')
assert not WORK.exists() and not REPO.exists() and not ENV.exists(),'Do not overwrite existing attempts or environments'
WORK.mkdir(mode=0o700);(WORK/'logs').mkdir();(WORK/'tmp').mkdir();REPO.parent.mkdir(exist_ok=True)
script=textwrap.dedent('''
import json,os,pathlib,shutil,subprocess,time
work=pathlib.Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1')
repo=pathlib.Path('/root/rivermind-data/external_models/Pi3MOS-SLAM_1b81d729c4259a5a775eb4aae41f959eea38ae14')
envpath=pathlib.Path('/opt/gamecam-pi3mos/envs/pi3mos-infer')
state={'stage':'STARTING','GPU_model_runs':0}
def save(): (work/'SETUP_STATE.json').write_text(json.dumps(state,indent=2)+'\\n')
def run(argv,label,timeout=900,extra=None):
 state['stage']=label;save()
 e=os.environ.copy();e.update(CUDA_VISIBLE_DEVICES='',GIT_TERMINAL_PROMPT='0',GIT_LFS_SKIP_SMUDGE='1',TMPDIR=str(work/'tmp'),PIP_NO_CACHE_DIR='1',PYTHONDONTWRITEBYTECODE='1')
 if extra:e.update(extra)
 with (work/'logs'/(label+'.log')).open('xb') as out:
  p=subprocess.run(argv,stdout=out,stderr=subprocess.STDOUT,env=e,timeout=timeout)
 state[label+'_exit_code']=p.returncode;save()
 if p.returncode:raise RuntimeError(label+' failed; preserve logs, no automatic retry')
try:
 save()
 run(['git','-c','credential.helper=','clone','--filter=blob:none','--no-checkout','https://github.com/PRBonn/Pi3MOS-SLAM.git',str(repo)],'CLONE_OFFICIAL',180)
 run(['git','-C',str(repo),'checkout','--detach','1b81d729c4259a5a775eb4aae41f959eea38ae14'],'PIN_OFFICIAL_COMMIT',180)
 assert subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()=='1b81d729c4259a5a775eb4aae41f959eea38ae14'
 run(['/opt/conda/bin/conda','create','--prefix',str(envpath),'--override-channels','-c','conda-forge','python=3.10','pip','-y'],'CREATE_INDEPENDENT_ENV',900)
 run([str(envpath/'bin/python'),'-m','pip','install','--no-cache-dir','--index-url','https://download.pytorch.org/whl/cu121','torch==2.3.1','torchvision==0.18.1'],'INSTALL_TORCH_CU121',1800)
 run([str(envpath/'bin/python'),'-m','pip','install','--no-cache-dir','numpy==1.26.4','pillow','einops','huggingface_hub==0.26.5','safetensors','plyfile','gdown','opencv-python-headless==4.10.0.84'],'INSTALL_MINIMAL_MODEL_DEPS',900)
 state['stage']='INDEPENDENT_ENV_READY';state['source_HEAD']=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
 state['source_worktree']=subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True)
 state['disk_free']={p:shutil.disk_usage(p).free for p in ['/','/root/rivermind-data']};save()
except Exception as e:
 state['stage']='SETUP_STOPPED';state['error']=str(e);save();raise
''')
path=WORK/'setup_independent.py';path.write_text(script)
log=(WORK/'logs/setup_controller.log').open('xb')
p=subprocess.Popen(['/usr/bin/python3','-u',str(path)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                   env={**os.environ,'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1'})
receipt={'controller_PID':p.pid,'work':str(WORK),'source':str(REPO),'environment':str(ENV),'GitHub_existing_authorization_retained':True,
         'model_runs':0,'full_SLAM_or_DPVO_extension_install':False}
(WORK/'SETUP_LAUNCH.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
