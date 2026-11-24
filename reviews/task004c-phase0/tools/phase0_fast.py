import sys,os,json,pathlib,subprocess,base64,shlex,hashlib,time
from datetime import datetime,timezone
ROOT=pathlib.Path(__file__).resolve().parents[1]
A=pathlib.Path(r'D:/aaa/GameCam-VO/experiments/DROID_W_TASK004A_GPU_SCREENING_20261123T082038066Z')
sys.path.insert(0,str(A/'bootstrap'))
from run_once import ssh_base,HOST,CREATE,verified
PRE=json.loads((A/'bootstrap/evidence/preflight.json').read_text())
lock=json.loads((ROOT/'evidence/HISTORICAL_IDENTITY_REFERENCE.json').read_text())
CODE=r'''
import sys,os,json,pathlib,subprocess,hashlib,shutil,time
from datetime import datetime,timezone
p=json.loads(sys.stdin.readline()); t=time.monotonic()
def cmd(args):
 try:
  q=subprocess.run(args,capture_output=True,text=True,timeout=25)
  return dict(command=args,exit_code=q.returncode,stdout=q.stdout,stderr=q.stderr)
 except Exception as e:return dict(command=args,error=repr(e))
def stat(x):
 q=pathlib.Path(x)
 if not q.is_file():return dict(path=x,exists=False)
 s=q.stat();return dict(path=x,exists=True,bytes=s.st_size,mtime_ns=s.st_mtime_ns,mode=oct(s.st_mode))
def sha(x):
 h=hashlib.sha256()
 with open(x,'rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
r=dict(utc=datetime.now(timezone.utc).isoformat(),hostname=cmd(['hostname']),gpu=cmd(['nvidia-smi','--query-gpu=index,name,uuid,memory.total,memory.free,memory.used,driver_version','--format=csv,noheader,nounits']),gpu_processes=cmd(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits']),nvidia_smi=cmd(['nvidia-smi']),memory=pathlib.Path('/proc/meminfo').read_text(),cuda_context_created=False,torch_imported=False)
r['files']={}
for x,expect in p['pins'].items():
 a=stat(x)
 if a['exists']:a.update(sha256=sha(x),expected_sha256=expect,match=sha(x)==expect)
 r['files'][x]=a
r['manifest']=stat(p['manifest']);r['python']=stat(p['python'])
for name,x in [('data','/root/rivermind-data'),('shm','/dev/shm')]:
 u=shutil.disk_usage(x);r[name]=dict(total_bytes=u.total,used_bytes=u.used,free_bytes=u.free)
for x in ['/sys/fs/cgroup/memory.max','/sys/fs/cgroup/memory/memory.limit_in_bytes']:
 if pathlib.Path(x).is_file():r.setdefault('cgroup',{})[x]=pathlib.Path(x).read_text().strip()
r['source_git']=cmd(['git','-C',p['source'],'rev-parse','HEAD'])
r['source_status']=cmd(['git','-C',p['source'],'status','--porcelain'])
r['cuda_versions']={}
for x in ['/usr/local/cuda/version.json','/usr/local/cuda-11.8/version.json','/usr/local/cuda/version.txt']:
 if pathlib.Path(x).is_file():r['cuda_versions'][x]=pathlib.Path(x).read_text()[:8000]
r['metadata']={}
for x in [p['root']+'/EXECUTION_IDENTITY.json',p['root']+'/evidence/PREFLIGHT_RAW.json',p['root']+'/release/REFERENCE_FILES.json','/root/rivermind-data/'+p['A_name']+'/EXECUTION_IDENTITY.json']:
 if pathlib.Path(x).is_file() and pathlib.Path(x).stat().st_size<200000:r['metadata'][x]=json.loads(pathlib.Path(x).read_text())
r['checkpoint_inventory']=[];r['inventory_errors']=[];r['run_roots']={}
roots=['/root/rivermind-data/'+p['A_name'],p['root'],'/root/rivermind-data/DROID_W_TASK003_VAL007_OBSERVATION_R1']
for root in roots:
 r['run_roots'][root]=dict(exists=pathlib.Path(root).is_dir(),children=sorted(x.name for x in pathlib.Path(root).iterdir()) if pathlib.Path(root).is_dir() else [])
 if not pathlib.Path(root).is_dir():continue
 for dp,ds,fs in os.walk(root,onerror=lambda e:r['inventory_errors'].append(str(e))):
  ds[:]=[d for d in ds if d not in ['source','pipeline','release','.git','__pycache__','runtime_cache','inputs','data','raw_archives','_chrome-profile']]
  for f in fs:
   q=pathlib.Path(dp)/f
   if q.suffix.lower() in ['.npz','.npy','.pt','.pth','.ckpt','.pkl','.pickle','.safetensors','.bin'] or any(w in f.lower() for w in ['snapshot','checkpoint','schedule']):r['checkpoint_inventory'].append(stat(str(q)))
r['processes']=cmd(['ps','-eo','pid,ppid,comm,args'])
r['seconds']=time.monotonic()-t
print(json.dumps(r,allow_nan=False))
'''
lock['A_name']=A.name
loader="import sys,base64;exec(compile(base64.b64decode(sys.stdin.readline()),'<task004c-readonly-phase0>','exec'))"
cmd='exec env CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /usr/bin/python3 -I -B -u -c '+shlex.quote(loader)
started=datetime.now(timezone.utc).isoformat()
q=subprocess.run(ssh_base(PRE)+['-o','ClearAllForwardings=yes',HOST,cmd],input=base64.b64encode(CODE.encode())+b'\n'+json.dumps(lock).encode()+b'\n',capture_output=True,creationflags=CREATE,timeout=200)
err=ROOT/'evidence/PHASE0_REMOTE.ssh.stderr.txt';err.write_bytes(q.stderr)
(ROOT/'evidence/PHASE0_REMOTE.stdout.txt').write_bytes(q.stdout)
trust=verified(err)
receipt=dict(started_utc=started,ended_utc=datetime.now(timezone.utc).isoformat(),exit_code=q.returncode,trust=trust,command_kind='read_only_no_model_no_torch',remote_gpu_executions=0)
(ROOT/'evidence/PHASE0_REMOTE_PROCESS.json').write_text(json.dumps(receipt,indent=2))
assert q.returncode==0 and all(trust.values()),receipt
r=json.loads(q.stdout);(ROOT/'evidence/PHASE0_REMOTE.json').write_text(json.dumps(r,indent=2))
print(json.dumps({k:r[k] for k in ['hostname','gpu','gpu_processes','data','shm','source_git','seconds']},indent=2))
print('CHECKPOINT_INVENTORY',json.dumps(r['checkpoint_inventory'],indent=2))
print('PINNED_FILES_MATCH',all(v.get('match') for v in r['files'].values()))
