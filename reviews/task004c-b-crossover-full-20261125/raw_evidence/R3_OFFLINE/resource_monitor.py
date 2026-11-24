import pathlib,time,json,subprocess,shutil,os
r=pathlib.Path(__file__).resolve().parent
with (r/'evidence/RESOURCE_TIMELINE.jsonl').open('x',buffering=1) as f:
 while not (r/'evidence/RESOURCE_MONITOR_STOP').exists():
  gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.free,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=20)
  stages=[]
  for p in (r/'attempts').iterdir():
   if p.name=='capture' or not p.is_dir() or (p/'PROCESS_RECEIPT.json').exists():continue
   stages.append(p.name)
  row={'unix':time.time(),'stages_in_progress':stages,'gpu_csv':gpu.stdout.strip(),'gpu_exit':gpu.returncode,'disk_free_bytes':shutil.disk_usage(r).free,'shm_used_bytes':shutil.disk_usage('/dev/shm').used,'shm_free_bytes':shutil.disk_usage('/dev/shm').free}
  for name,where in [('cgroup_current','/sys/fs/cgroup/memory.current'),('cgroup_peak','/sys/fs/cgroup/memory.peak')]:
   try:row[name]=int(pathlib.Path(where).read_text())
   except OSError:pass
  f.write(json.dumps(row)+'\n');time.sleep(5)
