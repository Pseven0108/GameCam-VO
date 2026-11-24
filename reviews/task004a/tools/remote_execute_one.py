import base64,hashlib,json,os,pathlib,shutil,signal,socket,subprocess,sys,time,uuid
from datetime import datetime,timezone
spec=json.loads(sys.stdin.readline());root=pathlib.Path(spec['root']);arm=spec['arm'];assert socket.gethostname()=='jupyter-yd6gks8uzfbxzdb4'
sys.path.insert(0,str(root/'release/tools'))
from contracts import ORDER,POLICY_SHA,CONFIG_SHA,INPUT_SHA,TENSOR_SHA,BITS
from attempt_contract import validate_attempt
from archive import inventory
utc=lambda:datetime.now(timezone.utc).isoformat()
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def put(path,doc):
 with path.open('x') as f:json.dump(doc,f,indent=2,allow_nan=False)
def gpu():
 p=subprocess.run(['nvidia-smi','--query-gpu=name,memory.free,memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=8);assert p.returncode==0,p.stderr
 return p.stdout.strip()
assert (root/'evidence/PREFLIGHT.json').is_file()
auth=root/'release/AUTHORIZATION.json';authorization=json.loads(auth.read_bytes());lock=json.loads((root/'evidence/LOCKDOWN.json').read_bytes())
assert authorization['order']==list(ORDER) and arm in ORDER
index=ORDER.index(arm)
for previous in ORDER[:index]:assert (root/'results'/previous/'COMPLETE.json').is_file(),previous
for later in ORDER[index:]:assert not (root/'results'/later).exists(),'attempt already claimed or wrong order'
for p,pin in lock['pins'].items():assert sha(p)==pin,p
policy=root/'release/policies'/f'{arm}.json';assert sha(policy)==POLICY_SHA[arm]
assert shutil.disk_usage(root).free>=13*1024**3
nv=gpu();assert 'RTX 3090' in nv and int(nv.split(',')[1])>=23000,nv
# Verified existing Rerun owner and loopback listeners, without starting another service.
service=spec['viewer'];native=service['native_identity'];proc=pathlib.Path('/proc')/str(native['pid'])
assert os.readlink(proc/'exe')==native['executable'] and os.readlink(proc/'cwd')==native['cwd']
rows=[]
for table in ['tcp','tcp6']:
 for line in pathlib.Path('/proc/net',table).read_text().splitlines()[1:]:
  f=line.split();address,port=f[1].split(':')
  if f[3]=='0A' and int(port,16) in [9875,9876,9877]:rows.append(dict(port=int(port,16),inode=f[9],address=address,table=table))
owned=[]
for f in (proc/'fd').iterdir():
 try:owned.append(os.readlink(f))
 except FileNotFoundError:pass
assert len(rows)==3 and all(r['address']=='0100007F' and r['table']=='tcp' and 'socket:['+r['inode']+']' in owned for r in rows)
# Confirm installed CUDA 11.8 toolkit identity without importing torch.
version=subprocess.run(['/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/cuda118/bin/nvcc','--version'],capture_output=True,text=True,timeout=8)
assert version.returncode==0 and 'release 11.8' in version.stdout
armdir=root/'results'/arm;armdir.mkdir();attempt=armdir/('attempt_001_'+uuid.uuid4().hex[:12]);attempt.mkdir()
shutil.copyfile(policy,attempt/'policy.json')
intent=dict(arm=arm,attempt_id=attempt.name,mode='REAL_GPU_SCREENING',authorization_sha256=sha(auth),policy_sha256=POLICY_SHA[arm],config_sha256=CONFIG_SHA,input_sha256=INPUT_SHA,output_dir=str(attempt),input_dir=str(pathlib.Path(lock['manifest']).parent),created_utc=utc(),recording_namespace=attempt.name,max_runs=1)
put(attempt/'LAUNCH_INTENT.json',intent)
env=dict(os.environ,GAMECAM_TASK004_AUTHORIZATION=str(auth),GAMECAM_TASK004_ATTEMPT=str(attempt),GAMECAM_TASK004_POLICY=str(policy),GAMECAM_TASK004_POLICY_SHA256=POLICY_SHA[arm],GAMECAM_TASK003_SEALED_CONFIG=lock['config'],GAMECAM_TASK003_OBSERVER_JSONL=str(attempt/'observer.jsonl'),PYTHONPATH=lock['pipeline']+':'+lock['source'],PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',TORCH_HOME=lock['torch_home'],HF_HOME=lock['hf_home'],HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',MPLBACKEND='Agg',CUDA_VISIBLE_DEVICES='0',XDG_CACHE_HOME=str(attempt/'runtime_cache'),RERUN_NO_ANALYTICS='1')
argv=[lock['python'],'-B',str(pathlib.Path(lock['pipeline'])/'task004_run_segment.py'),lock['manifest'],str(attempt),'--weights',lock['weights'][0]]
put(attempt/'RUNTIME_LAUNCH_CONFIG.json',dict(argv=argv,cwd=lock['source'],env_overrides={k:env[k] for k in ['CUDA_VISIBLE_DEVICES','PYTHONPATH','TORCH_HOME','HF_HOME','GAMECAM_TASK004_AUTHORIZATION','GAMECAM_TASK004_POLICY','GAMECAM_TASK004_POLICY_SHA256','GAMECAM_TASK003_SEALED_CONFIG']},cuda_version=version.stdout,rerun=service))
started=time.monotonic();failure=None;peak_gpu=0;peak_rss=0
with (attempt/'process.stdout.txt').open('xb') as out,(attempt/'process.stderr.txt').open('xb') as err,(attempt/'resource.jsonl').open('x') as resource:
 p=subprocess.Popen(argv,cwd=lock['source'],env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
 put(attempt/'LAUNCH_RECEIPT.json',dict(intent,pid=p.pid,argv=argv,launched_utc=utc()))
 print(json.dumps(dict(event='GPU_STARTED',arm=arm,pid=p.pid,attempt=str(attempt))),flush=True)
 while p.poll() is None:
  try:
   nv=gpu();used=int(nv.split(',')[2]);peak_gpu=max(peak_gpu,used);free=shutil.disk_usage(root).free
   if free<10*1024**3:raise RuntimeError('DISK_SAFETY_FLOOR')
   if not proc.exists() or os.readlink(proc/'exe')!=native['executable']:raise RuntimeError('RERUN_SERVICE_LOST')
   try:state=json.loads((attempt/'progress.json').read_bytes()) if (attempt/'progress.json').exists() else {}
   except json.JSONDecodeError:state={'state':'PROGRESS_WRITE_IN_FLIGHT'}
   resource.write(json.dumps(dict(utc=utc(),elapsed_s=time.monotonic()-started,gpu=nv,free_bytes=free,progress=state))+'\n');resource.flush()
   if time.monotonic()-started>3600:raise TimeoutError('One-arm runtime exceeded 1 hour')
  except Exception as e:
   failure=repr(e);os.killpg(p.pid,signal.SIGTERM);break
  time.sleep(2)
 rc=p.wait(timeout=30)
put(attempt/'PROCESS_RECEIPT.json',dict(pid=p.pid,mode=intent['mode'],exit_code=rc,elapsed_s=time.monotonic()-started,peak_gpu_used_mib=peak_gpu,finished_utc=utc(),failure=failure))
assert rc==0 and failure is None,'RUN_FAILED: '+str(rc)+' '+str(failure)
try:
 trace,poses,kfs=validate_attempt(attempt,arm,POLICY_SHA[arm],lock['config'])
except Exception as e:
 put(attempt/'VALIDATION_FAILED.json',dict(error=repr(e),utc=utc()));raise
summary=dict(arm=arm,attempt=str(attempt),status='COMPLETE',elapsed_s=time.monotonic()-started,peak_gpu_used_mib=peak_gpu,keyframes=len(kfs),ba_calls=len(trace.calls),poses=len(poses),observer_sha256=trace.sha256,policy_sha256=POLICY_SHA[arm],no_retry=True)
put(attempt/'OUTPUT_INTEGRITY.json',dict(files=inventory(attempt),validated_utc=utc()))
put(armdir/'COMPLETE.json',summary)
print(json.dumps(dict(event='GPU_COMPLETE',**summary)),flush=True)
