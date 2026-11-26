"""CPU-only final preservation read; no model call or GPU context creation."""
import json,pathlib,hashlib,subprocess,shutil
base=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408')
root=pathlib.Path('/root/rivermind-data/GAMECAM_TASK006A_R2_1_GPU_PILOT_20261126_R1')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
files=[base/'data/torch_hub/checkpoints/metric_depth_vit_large_800k.pth',base/'source/DROID-W/src/utils/mono_priors/metric_depth_estimators.py']
inputs=[]
for name in ['smoke_qualified','pilot']:
 for r in json.loads((root/'control'/(name+'_manifest.json')).read_text())['samples']:
  p=pathlib.Path(r['rgb_path']);inputs.append({'path':str(p),'sha256':sha(p),'matches_manifest':sha(p)==r['rgb_sha256']})
out={'files':[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files],
 'hub_HEAD':subprocess.check_output(['git','-C',str(base/'data/torch_hub/yvanyin_metric3d_main'),'rev-parse','HEAD'],text=True).strip(),
 'hub_tracked_status':subprocess.check_output(['git','-C',str(base/'data/torch_hub/yvanyin_metric3d_main'),'status','--short','--untracked-files=no'],text=True),
 'input_files':inputs,'all_inputs_unchanged':all(x['matches_manifest'] for x in inputs),
 'GPU_processes':subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader'],text=True),
 'free_data_bytes':shutil.disk_usage(root).free,'models_loaded_by_this_check':False,'shutdown_performed':False}
print(json.dumps(out,indent=2))
