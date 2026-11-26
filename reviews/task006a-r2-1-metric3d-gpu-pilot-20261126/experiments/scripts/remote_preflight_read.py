"""Read-only hardware/package/checkpoint inventory, before any torch import."""
import hashlib,json,pathlib,subprocess,shutil,socket
BASE=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408')
HUB=BASE/'data/torch_hub/yvanyin_metric3d_main'
def run(args):
 try:
  p=subprocess.run(args,capture_output=True,text=True,timeout=20)
  return {'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
 except Exception as e:return {'error':str(e)}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
paths=[BASE/'data/torch_hub/checkpoints/metric_depth_vit_large_800k.pth',BASE/'source/DROID-W/src/utils/mono_priors/metric_depth_estimators.py']
rows=[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths if p.is_file()]
py='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'
pkg="import json,importlib.metadata as m; print(json.dumps({x:m.version(x) for x in ['torch','torchvision','numpy','opencv-python','timm','Pillow']},indent=2))"
out={'hostname':socket.gethostname(),'GPU':run(['nvidia-smi','--query-gpu=name,uuid,driver_version,memory.total,memory.free','--format=csv,noheader,nounits']),
 'GPU_full':run(['nvidia-smi']),'GPU_processes':run(['nvidia-smi','--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader']),
 'process_names':run(['ps','-eo','pid,comm']),
 'filesystems':{x:{'total':shutil.disk_usage(x).total,'free':shutil.disk_usage(x).free} for x in ['/root/rivermind-data','/dev/shm']},
 'hub_HEAD':run(['git','-C',str(HUB),'rev-parse','HEAD']),
 'hub_status':run(['git','-C',str(HUB),'status','--short','--untracked-files=no']),
 'DROID_W_HEAD':run(['git','-C',str(BASE/'source/DROID-W'),'rev-parse','HEAD']),
 'files':rows,'package_metadata':run([py,'-B','-c',pkg]),
 'paths':{str(p):[{'name':q.name,'directory':q.is_dir()} for q in sorted(p.iterdir())] for p in [BASE/'data',BASE/'data/datasets',pathlib.Path('/root/rivermind-data/VIPER_MATCHED_DUAL_BASELINE_R2')] if p.is_dir()},
 'models_loaded':False,'CUDA_context_initialized':False,'checkpoint_deserialized':False}
print(json.dumps(out,indent=2))
