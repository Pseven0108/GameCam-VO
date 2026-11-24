import pathlib,json,sys,base64,shlex,subprocess
from datetime import datetime,timezone
ROOT=pathlib.Path(__file__).resolve().parents[1]
A=pathlib.Path(r'D:/aaa/GameCam-VO/experiments/DROID_W_TASK004A_GPU_SCREENING_20261123T082038066Z');sys.path.insert(0,str(A/'bootstrap'))
from run_once import ssh_base,HOST,CREATE,verified
pre=json.loads((A/'bootstrap/evidence/preflight.json').read_text());data=json.loads((ROOT/'evidence/PHASE0_LOCAL_ARCHIVE_VALIDATION.json').read_text())
checks={}
for arm in ['E0','E1']:
 meta=data[arm]['small_metadata'];base=meta['LAUNCH_RECEIPT.json']['output_dir']
 for f in ['observer.jsonl','native/video.npz','native_config.yaml','trajectory.npz']:
  checks[base+'/'+f]=meta['_TASK004A_ARCHIVE_MANIFEST.json']['files'][f]['sha256']
CODE=r'''
import sys,json,pathlib,hashlib,subprocess,shutil
from datetime import datetime,timezone
p=json.loads(sys.stdin.readline());out={}
for name,expected in p.items():
 h=hashlib.sha256()
 with open(name,'rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 out[name]=dict(sha256=h.hexdigest(),expected_sha256=expected,unchanged=h.hexdigest()==expected)
q=subprocess.run(['nvidia-smi','--query-gpu=name,memory.free,memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=15)
a=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=15)
u=shutil.disk_usage('/root/rivermind-data')
print(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),protected_files=out,all_unchanged=all(v['unchanged'] for v in out.values()),gpu_query_exit=q.returncode,gpu=q.stdout,gpu_stderr=q.stderr,gpu_compute_query_exit=a.returncode,gpu_compute_processes=a.stdout,free_data_bytes=u.free,remote_writes=0,model_starts=0,cuda_contexts_created=0,shutdown=False,reboot=False),indent=2))
'''
loader="import sys,base64;exec(compile(base64.b64decode(sys.stdin.readline()),'<task004c-final-readonly>','exec'))"
cmd='exec env CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /usr/bin/python3 -I -B -u -c '+shlex.quote(loader)
q=subprocess.run(ssh_base(pre)+['-o','ClearAllForwardings=yes',HOST,cmd],input=base64.b64encode(CODE.encode())+b'\n'+json.dumps(checks).encode()+b'\n',capture_output=True,creationflags=CREATE,timeout=100)
err=ROOT/'evidence/FINAL_REMOTE.ssh.stderr.txt';err.write_bytes(q.stderr);(ROOT/'evidence/FINAL_REMOTE.stdout.txt').write_bytes(q.stdout);trust=verified(err)
(ROOT/'evidence/FINAL_REMOTE_PROCESS.json').write_text(json.dumps(dict(exit_code=q.returncode,trust=trust,utc=datetime.now(timezone.utc).isoformat()),indent=2))
assert q.returncode==0 and all(trust.values()),q.returncode
r=json.loads(q.stdout);assert r['all_unchanged'];(ROOT/'evidence/FINAL_REMOTE_PRESERVATION.json').write_text(json.dumps(r,indent=2))
print(json.dumps(dict(all_unchanged=r['all_unchanged'],protected_files=len(r['protected_files']),gpu=r['gpu'],gpu_compute_processes=r['gpu_compute_processes'],free_data_bytes=r['free_data_bytes'],shutdown=r['shutdown']),indent=2))
