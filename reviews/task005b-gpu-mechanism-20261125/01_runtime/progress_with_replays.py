import pathlib,json,shutil,subprocess
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1');out={'disk_free':shutil.disk_usage(r).free,'shm_free':shutil.disk_usage('/dev/shm').free,'attempts':{}}
for a in (r/'attempts').iterdir():
 q={}
 for f in ['LAUNCH_RECEIPT.json','RESTORE_RECEIPT.json','SUCCESS.json','PROCESS_RECEIPT.json']:
  if (a/f).exists():q[f]=json.loads((a/f).read_text())
 for f in ['stdout.txt','stderr.txt']:
  p=a/f
  if p.exists():
   with p.open('rb') as v:v.seek(max(0,p.stat().st_size-2500));q[f]=v.read().decode(errors='replace')
 q['captures']=[{'name':x.name,'bytes':sum(v.stat().st_size for v in x.iterdir() if v.is_file())} for x in (r/'snapshots').glob(a.name+'_*') if x.is_dir()]
 out['attempts'][a.name]=q
out['replays']={p.name:{n:json.loads((p/n).read_text()) for n in ['LAUNCH_RECEIPT.json','PROCESS_RECEIPT.json'] if (p/n).exists()} for p in (r/'evidence').glob('REPLAY_*') if p.is_dir()}
out['gpu']=subprocess.run(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader'],capture_output=True,text=True).stdout
print(json.dumps(out))
