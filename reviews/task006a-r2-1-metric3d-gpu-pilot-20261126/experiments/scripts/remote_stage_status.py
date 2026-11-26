import json,pathlib,subprocess,shutil
root=pathlib.Path('/root/rivermind-data/GAMECAM_TASK006A_R2_1_GPU_PILOT_20261126_R1')
out={'free_data_bytes':shutil.disk_usage(root).free}
for stage in ['smoke','smoke_qualified','pilot']:
 p=root/stage/'INFERENCE_RECEIPT.json'
 out[stage]={'receipt':json.loads(p.read_text()) if p.is_file() else None}
 for kind in ['stdout','stderr']:
  q=root/'logs'/(stage+'.'+kind+'.txt')
  if q.exists():out[stage][kind+'_tail']=q.read_text(errors='replace')[-4500:]
 out[stage]['files']=[{'name':x.name,'bytes':x.stat().st_size} for x in sorted((root/stage).glob('*')) if x.is_file()]
out['GPU']=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.used,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True)
print(json.dumps(out,indent=2))
