import pathlib,json,subprocess,shutil
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1')
out={'disk_free':shutil.disk_usage(r).free,'replays':{}}
for p in (r/'evidence').glob('REPLAY_*'):
 q={}
 for n in ['LAUNCH_RECEIPT.json','PROCESS_RECEIPT.json']:
  if (p/n).is_file():q[n]=json.loads((p/n).read_text())
 for n in ['stdout.txt','stderr.txt']:
  f=p/n
  if f.exists():
   with f.open('rb') as stream:stream.seek(max(0,f.stat().st_size-5500));q[n]=stream.read().decode(errors='replace')
 res=r/'results'/p.name.removeprefix('REPLAY_')
 q['files']=[{'name':v.name,'bytes':v.stat().st_size} for v in res.glob('*') if v.is_file()]
 for n in ['SUCCESS.json','ENDPOINT_FAILURE.json']:
  if (res/n).is_file():q[n]=json.loads((res/n).read_text())
 out['replays'][p.name]=q
out['gpu']=subprocess.run(['nvidia-smi','--query-compute-apps=pid,used_gpu_memory','--format=csv,noheader'],capture_output=True,text=True).stdout
print(json.dumps(out))
