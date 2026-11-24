import pathlib,sys,os,json,time,shutil,hashlib,subprocess,signal,socket,uuid,re
from datetime import datetime,timezone
s=json.loads(sys.stdin.readline());root=pathlib.Path(s['root']);seed=int(s['seed']);arm=s['arm'];assert socket.gethostname()=='jupyter-yd6gks8uzfbxzdb4'
sys.path.insert(0,str(root/'release/tools'))
from contracts import POLICY_SHA,CONFIG_SHA,INPUT_SHA,TENSOR_SHA,BITS
from attempt_contract import validate_attempt
from archive import inventory,seal
utc=lambda:datetime.now(timezone.utc).isoformat()
def put(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2,allow_nan=False)
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def gpu():
 p=subprocess.run(['nvidia-smi','--query-gpu=name,memory.free,memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=8);assert p.returncode==0,p.stderr;return p.stdout.strip()
def listeners():
 out=[]
 for name in ('tcp','tcp6'):
  for line in pathlib.Path('/proc/net',name).read_text().splitlines()[1:]:
   f=line.split();addr,port=f[1].split(':')
   if f[3]=='0A' and int(port,16) in [9875,9876,9877]:out.append(dict(port=int(port,16),address=addr,table=name,inode=f[9]))
 return out
lock=json.loads((root/'evidence/LOCKDOWN.json').read_text());auth=root/'release/AUTHORIZATION.json';approval=json.loads(auth.read_text());pairs=[(sd,a) for sd in (44,45) for a in approval['orders'][str(sd)]];ix=pairs.index((seed,arm))
for sd,a in pairs[:ix]:assert (root/'results'/('seed'+str(sd))/a/'COMPLETE.json').is_file()
for sd,a in pairs[ix:]:assert not (root/'results'/('seed'+str(sd))/a).exists(),'attempt claimed; retries prohibited'
for p,h in lock['pins'].items():assert sha(p)==h,p
policy=root/'release/policies'/(arm+'.json');assert sha(policy)==POLICY_SHA[arm]
assert shutil.disk_usage(root).free>=13*1024**3,'STORAGE_BLOCKED'
nv=gpu();assert 'RTX 3090' in nv and int(nv.split(',')[1])>=23000,nv
assert not listeners(),'RERUN_PORT_CONFLICT'
armdir=root/'results'/('seed'+str(seed))/arm;armdir.mkdir(parents=True);at=armdir/('attempt_001_'+uuid.uuid4().hex[:12]);at.mkdir();shutil.copyfile(policy,at/'policy.json')
intent=dict(arm=arm,seed=seed,attempt_id=at.name,mode='REAL_GPU_CONFIRMATORY',authorization_sha256=sha(auth),policy_sha256=POLICY_SHA[arm],config_sha256=CONFIG_SHA,input_sha256=INPUT_SHA,output_dir=str(at),input_dir=str(pathlib.Path(lock['manifest']).parent),created_utc=utc(),recording_namespace='seed'+str(seed)+'_'+arm+'_'+at.name,max_runs=1)
put(at/'LAUNCH_INTENT.json',intent)
service=None;child=None;error=None;started=time.monotonic();peakgpu=0;peakshm=0;modelrc=None;view=None
try:
 argv=s['viewer_argv']+['--save',str(at/'native_rerun.rrd')]
 with (at/'rerun_service.stdout.txt').open('xb') as so,(at/'rerun_service.stderr.txt').open('xb') as se:
  service=subprocess.Popen(argv,cwd=at,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',RERUN_NO_ANALYTICS='1'),stdout=so,stderr=se,start_new_session=True)
  pp=pathlib.Path('/proc')/str(service.pid)
  for _ in range(100):
   assert service.poll() is None,'RERUN_SERVICE_EXIT'
   ports=listeners()
   if {x['port'] for x in ports} in ({9875},{9875,9876,9877}):
    fds=[]
    for f in (pp/'fd').iterdir():
     try:fds.append(os.readlink(f))
     except FileNotFoundError:pass
    assert all(x['address']=='0100007F' and x['table']=='tcp' and 'socket:['+x['inode']+']' in fds for x in ports)
    view=dict(pid=service.pid,argv=argv,listeners=ports,browser_rendering='NOT_REQUIRED_NOT_VERIFIED',recording_path=str(at/'native_rerun.rrd'));break
   time.sleep(.1)
  assert view,'RERUN_NO_LOOPBACK_LISTENER';put(at/'RERUN_SERVICE_RECEIPT.json',view)
  env=dict(os.environ,GAMECAM_TASK004_AUTHORIZATION=str(auth),GAMECAM_TASK004_ATTEMPT=str(at),GAMECAM_TASK004_POLICY=str(policy),GAMECAM_TASK004_POLICY_SHA256=POLICY_SHA[arm],GAMECAM_TASK004B_SEED=str(seed),GAMECAM_TASK003_SEALED_CONFIG=lock['config'],GAMECAM_TASK003_OBSERVER_JSONL=str(at/'observer.jsonl'),PYTHONPATH=lock['pipeline']+':'+lock['source'],PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',TORCH_HOME=lock['torch_home'],HF_HOME=lock['hf_home'],HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',MPLBACKEND='Agg',CUDA_VISIBLE_DEVICES='0',XDG_CACHE_HOME=str(at/'runtime_cache'),RERUN_NO_ANALYTICS='1')
  argv=[lock['python'],'-B',str(pathlib.Path(lock['pipeline'])/'task004_run_segment.py'),lock['manifest'],str(at),'--weights',lock['weights'][0]]
  put(at/'RUNTIME_LAUNCH_CONFIG.json',dict(argv=argv,cwd=lock['source'],seed=seed,base_config_sha256=CONFIG_SHA,env_overrides={k:env[k] for k in ['CUDA_VISIBLE_DEVICES','PYTHONPATH','GAMECAM_TASK004B_SEED','GAMECAM_TASK004_AUTHORIZATION','GAMECAM_TASK004_POLICY','GAMECAM_TASK004_POLICY_SHA256','GAMECAM_TASK003_SEALED_CONFIG']},rerun=view))
  started=time.monotonic()
  with (at/'process.stdout.txt').open('xb') as out,(at/'process.stderr.txt').open('xb') as err,(at/'resource.jsonl').open('x') as resource:
   child=subprocess.Popen(argv,cwd=lock['source'],env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
   put(at/'LAUNCH_RECEIPT.json',dict(intent,pid=child.pid,argv=argv,launched_utc=utc()))
   print(json.dumps(dict(event='GPU_STARTED',seed=seed,arm=arm,pid=child.pid,attempt=str(at))),flush=True)
   while child.poll() is None:
    nv=gpu();peakgpu=max(peakgpu,int(nv.split(',')[2]));free=shutil.disk_usage(root).free;shm=shutil.disk_usage('/dev/shm');peakshm=max(peakshm,shm.used)
    assert free>=10*1024**3,'DISK_BELOW_SAFETY_FLOOR'
    assert service.poll() is None,'RERUN_RECORDING_SERVICE_LOST'
    assert time.monotonic()-started<3600,'RUN_TIMEOUT'
    try:progress=json.loads((at/'progress.json').read_text()) if (at/'progress.json').exists() else {}
    except json.JSONDecodeError:progress=dict(state='WRITE_IN_PROGRESS')
    resource.write(json.dumps(dict(utc=utc(),elapsed_s=time.monotonic()-started,gpu=nv,free_bytes=free,shm_used_bytes=shm.used,progress=progress))+chr(10));resource.flush();time.sleep(2)
   modelrc=child.wait();assert modelrc==0,'MODEL_EXIT_'+str(modelrc)
except BaseException as exc:
 error=repr(exc)
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:modelrc=child.wait(timeout=30)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);modelrc=child.wait(timeout=10)
 raise
finally:
 if child is not None:
  put(at/'PROCESS_RECEIPT.json',dict(pid=child.pid,mode=intent['mode'],exit_code=modelrc,elapsed_s=time.monotonic()-started,peak_gpu_used_mib=peakgpu,peak_shm_used_bytes=peakshm,finished_utc=utc(),failure=error))
 if service is not None and service.poll() is None:
  service.terminate()
  try:service.wait(timeout=15)
  except subprocess.TimeoutExpired:service.kill();service.wait(timeout=5)
 time.sleep(.2);put(at/'RERUN_SERVICE_CLEANUP.json',dict(pid=None if service is None else service.pid,exit_code=None if service is None else service.poll(),ports_after=listeners(),error=error))
assert child is not None and modelrc==0 and error is None
rrd=at/'native_rerun.rrd';assert rrd.is_file() and rrd.stat().st_size>0,'MISSING_RECORDING'
with (at/'rerun_recording_print.txt').open('wb') as out,(at/'rerun_recording_print.stderr.txt').open('wb') as err:
 p=subprocess.run([s['viewer_argv'][0],'rrd','print',str(rrd)],stdout=out,stderr=err,timeout=180)
assert p.returncode==0,'CORRUPT_RRD'
rrtext=(at/'rerun_recording_print.txt').read_text();ids=sorted(set(re.findall('id: "([^"]+)"',rrtext)))
assert len(ids)==1,'RECORDING_ID_NOT_UNIQUE'
put(at/'RERUN_RECORDING_VALIDATION.json',dict(sha256=sha(rrd),bytes=rrd.stat().st_size,decode_exit_code=p.returncode,recording_ids=ids,browser_rendering='NOT_REQUIRED_NOT_VERIFIED',native_writer_unchanged=True,server_side_recording_added=True))
trace,poses,kfs=validate_attempt(at,arm,POLICY_SHA[arm],lock['config'])
put(at/'OUTPUT_INTEGRITY.json',dict(files=inventory(at),validated_utc=utc()))
summary=dict(seed=seed,arm=arm,attempt=str(at),status='COMPLETE',keyframes=len(kfs),ba_calls=len(trace.calls),poses=len(poses),observer_sha256=trace.sha256,policy_sha256=POLICY_SHA[arm],peak_gpu_used_mib=peakgpu,peak_shm_used_bytes=peakshm,no_retry=True,model_elapsed_s=json.loads((at/'PROCESS_RECEIPT.json').read_text())['elapsed_s'])
z=root/'sealed_results'/('seed'+str(seed)+'_'+arm+'_'+at.name+'.zip');arch=seal(at,z,at.name);arch.update(seed=seed,arm=arm)
put(at.parent/'ARCHIVE_RECEIPT.json',arch);put(armdir/'COMPLETE.json',summary)
print(json.dumps(dict(event='GPU_COMPLETE_AND_SEALED',**summary,archive=arch)),flush=True)
