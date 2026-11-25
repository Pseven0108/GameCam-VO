import pathlib,subprocess,json,shutil,socket
hist=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE')
def run(a):
 try:
  p=subprocess.run(a,capture_output=True,text=True,timeout=20);return {'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
 except Exception as e:return {'error':str(e)}
out={'hostname':socket.gethostname(),'disk':dict(zip(('total','used','free'),shutil.disk_usage('/root/rivermind-data'))),'shm':dict(zip(('total','used','free'),shutil.disk_usage('/dev/shm'))),'gpu':run(['nvidia-smi','--query-gpu=name,memory.total,memory.free,uuid,driver_version','--format=csv,noheader']),'gpu_processes':run(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader']),'history_exists':hist.exists()}
out['source_head']=run(['git','-C',str(hist/'source_candidate'),'rev-parse','HEAD']);out['source_status']=run(['git','-C',str(hist/'source_candidate'),'status','--porcelain'])
out['top_dirs']=[str(p) for p in pathlib.Path('/root').glob('*') if p.is_dir() and not p.name.startswith('.')]
out['history_top']=[{'name':p.name,'directory':p.is_dir()} for p in hist.glob('*')]
out['processes']=run(['ps','-eo','pid,comm,args'])
print(json.dumps(out))
