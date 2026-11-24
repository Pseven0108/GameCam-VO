"""Single-operation supervisor; exclusive attempts, no retries, no shutdown."""
import os,sys,json,pathlib,subprocess,time,shutil,hashlib,traceback
R=pathlib.Path(__file__).resolve().parents[1];A=json.loads((R/'AUTHORIZATION.json').read_text());L=A['lock'];FLOOR=10*1024**3

def put(p,x):
 with pathlib.Path(p).open('x') as f:json.dump(x,f,indent=2,allow_nan=False)
def atomic(p,x):
 q=pathlib.Path(str(p)+'.writing');q.write_text(json.dumps(x,indent=2));os.replace(q,p)
def resources():
 r={'time_unix':time.time(),'disk_free':shutil.disk_usage(R).free,'shm_used':shutil.disk_usage('/dev/shm').used}
 q=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10)
 r['nvidia_smi_exit']=q.returncode;r['gpu_memory_mib']=q.stdout.strip();return r

def main():
 mode,key=sys.argv[1:3]
 assert mode in ('capture','replay')
 if mode=='capture':
  assert key in ('E0','E1');at=R/'captures'/key
  argv=[L['python'],'-B','-u',str(R/'control/task004c_prefix.py'),L['manifest'],str(at),'--weights',L['weights'][0]]
  policy=R/'policies'/(key+'.json');psha=hashlib.sha256(policy.read_bytes()).hexdigest()
 else:
  arm,flag=key.split('_D');D=int(flag);assert arm in ('E0','E1') and D in (0,1);at=R/'replays'/key
  argv=[L['python'],'-B','-u',str(R/'control/replay_one.py'),str(R/'captures'/arm/'checkpoint'),str(at),str(D)]
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='0',PYTHONPATH=str(R/'control')+':'+L['pipeline']+':'+L['source'],PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',TORCH_HOME=str(pathlib.Path(L['weights'][1]).parent.parent),HF_HOME=str(pathlib.Path(L['weights'][3]).parents[5]),HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',MPLBACKEND='Agg',XDG_CACHE_HOME=str(at/'runtime_cache'),RERUN_NO_ANALYTICS='1',GAMECAM_TASK004C_AUTHORIZATION=str(R/'AUTHORIZATION.json'),GAMECAM_TASK004C_ATTEMPT=str(at))
 # Freeze the exact original offline asset directories.
 env['TORCH_HOME']='/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/torch_hub'
 env['HF_HOME']='/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/huggingface'
 if mode=='capture':env.update(GAMECAM_TASK004_POLICY=str(policy),GAMECAM_TASK004_POLICY_SHA256=psha,GAMECAM_TASK003_SEALED_CONFIG=L['config'],GAMECAM_TASK003_OBSERVER_JSONL=str(at/'observer.jsonl'))
 r=resources();assert r['disk_free']>=FLOOR+1024**3
 if mode=='capture':assert int(r['gpu_memory_mib'].split(',')[1])>=23000
 status={'mode':mode,'key':key,'phase':'starting','before':r,'argv':argv,'cwd':L['source'],'attempt_dir':str(at)}
 atomic(at/'STATUS.json',status);started=time.monotonic();peak_shm=0;peak_gpu=0;minimum_free=r['disk_free']
 try:
  with (at/'stdout.txt').open('xb') as so,(at/'stderr.txt').open('xb') as se:
   p=subprocess.Popen(argv,cwd=L['source'],env=env,stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True)
   status.update(phase='running',pid=p.pid);atomic(at/'STATUS.json',status)
   while p.poll() is None:
    r=resources();peak_shm=max(peak_shm,r['shm_used']);minimum_free=min(minimum_free,r['disk_free']);peak_gpu=max(peak_gpu,int(r['gpu_memory_mib'].split(',')[0] or 0));status.update(phase='running',last=r,elapsed=time.monotonic()-started)
    atomic(at/'STATUS.json',status)
    if r['disk_free']<FLOOR:raise RuntimeError('STORAGE_FLOOR_BREACHED')
    if time.monotonic()-started>1500:raise RuntimeError('BOUNDED_OPERATION_EXCEEDED_1500S')
    time.sleep(2)
   exitcode=p.returncode
  expected=at/('CAPTURE_COMPLETE.json' if mode=='capture' else 'REPLAY_COMPLETE.json')
  status.update(phase='complete' if exitcode==0 and expected.is_file() else 'failed',exit_code=exitcode,elapsed=time.monotonic()-started,expected_completion=expected.is_file(),peak_shm_bytes=peak_shm,peak_gpu_mib=peak_gpu,minimum_disk_free=minimum_free,after=resources())
  atomic(at/'STATUS.json',status)
  if status['phase']!='complete':raise RuntimeError('operation failed; no retry allowed')
 except Exception as e:
  status.update(phase='failed',exception=repr(e),traceback=traceback.format_exc(),elapsed=time.monotonic()-started)
  atomic(at/'STATUS.json',status)
  # Only terminate our own attempt on a supervising failure.
  if 'p' in locals() and p.poll() is None:
   import signal
   os.killpg(p.pid,signal.SIGTERM)
  raise
if __name__=='__main__':main()
