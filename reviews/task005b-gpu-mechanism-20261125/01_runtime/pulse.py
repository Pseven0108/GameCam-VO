"""Read-only compact progress; no process arguments or access-bearing URLs."""
import pathlib,json,subprocess,shutil,time
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1')
out={'unix':time.time(),'disk_free_bytes':shutil.disk_usage(r).free,
     'shm_free_bytes':shutil.disk_usage('/dev/shm').free,'prefixes':{},'replays':{}}
for p in sorted((r/'attempts').iterdir()):
    row={}
    for name in ('RESTORE_RECEIPT.json','SUCCESS.json','PROCESS_RECEIPT.json'):
        if (p/name).is_file():row[name]=json.loads((p/name).read_text())
    for name in ('stdout.txt','stderr.txt'):
        q=p/name
        if q.exists():
            with q.open('rb') as stream:
                stream.seek(max(0,q.stat().st_size-600));row[name]=stream.read().decode(errors='replace')
    trace=p/'native_control.jsonl'
    if trace.is_file():
        with trace.open('rb') as stream:
            stream.seek(max(0,trace.stat().st_size-500));row['trace_tail']=stream.read().decode(errors='replace')
    out['prefixes'][p.name]=row
for p in sorted((r/'evidence').glob('REPLAY_CONTEXT02_*')):
    q=p/'PROCESS_RECEIPT.json'
    out['replays'][p.name]=json.loads(q.read_text()) if q.exists() else 'RUNNING'
out['gpu']=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.used,utilization.gpu','--format=csv,noheader'],text=True).strip()
out['gpu_compute_pids']=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,used_gpu_memory','--format=csv,noheader'],text=True).strip()
print(json.dumps(out))
