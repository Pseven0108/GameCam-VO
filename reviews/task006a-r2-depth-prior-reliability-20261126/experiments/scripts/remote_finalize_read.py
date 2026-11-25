"""Remote read-only final identity check. No torch import or checkpoint load."""
import hashlib,json,pathlib,subprocess,shutil
BASE=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408')
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
paths=[BASE/'data/torch_hub/checkpoints/metric_depth_vit_large_800k.pth',
       BASE/'source/DROID-W/src/utils/mono_priors/metric_depth_estimators.py']
rows=[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths]
try:
 p=subprocess.run(['nvidia-smi','--query-gpu=name,memory.free','--format=csv,noheader'],capture_output=True,text=True,timeout=15)
 gpu={'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
except Exception as e:gpu={'error':str(e)}
print(json.dumps({'files':rows,'hub_HEAD':subprocess.check_output(['git','-C',str(BASE/'data/torch_hub/yvanyin_metric3d_main'),'rev-parse','HEAD'],text=True).strip(),
 'GPU_read_only':gpu,'free_data_bytes':shutil.disk_usage('/root/rivermind-data').free,
 'checkpoint_deserialized':False,'torch_imported':False,'CUDA_initialized':False,'remote_mutation':False},indent=2))
