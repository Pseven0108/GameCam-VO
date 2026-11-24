"""Resource and identity readback before any model is started."""
import json,pathlib
from remote_cpu import ROOT,call
code=r'''
import hashlib,json,pathlib,subprocess,shutil,socket,os,importlib.metadata
origin=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_NATIVE_RELEASE_FIXES_20261124_R1')
src=origin/'source_candidate'
lock=json.loads((origin/'configs/identity_lock.json').read_text())
def cmd(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=25)
 return {'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
pins={**lock['remote_pins'],**lock['execution_source_pins']}
verified={p:{'exists':pathlib.Path(p).is_file(),'expected':v,'actual':sha(p) if pathlib.Path(p).is_file() else None} for p,v in pins.items()}
issues=[]
if not all(v['expected']==v['actual'] for v in verified.values()):issues.append('HISTORICAL_PROTECTED_IDENTITY_MISMATCH')
head=cmd(['git','-C',str(src),'rev-parse','HEAD'])
status=cmd(['git','-C',str(src),'status','--porcelain','--untracked-files=no'])
if head['stdout'].strip()!='668a88c74c7f7a88a572679d2bd8e86c0a05514b' or status['stdout'] or status['exit_code']:issues.append('REVIEWED_CANDIDATE_MISMATCH')
gpu=cmd(['nvidia-smi','--query-gpu=name,memory.total,memory.free,driver_version,uuid','--format=csv,noheader,nounits'])
apps=cmd(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits'])
if gpu['exit_code']:issues.append('GPU_STATUS_UNAVAILABLE')
else:
 rows=gpu['stdout'].strip().splitlines()
 if len(rows)!=1 or 'RTX 3090' not in rows[0]:issues.append('SINGLE_3090_NOT_CONFIRMED')
 elif float(rows[0].split(',')[2])<23000:issues.append('GPU_FREE_MEMORY_BELOW_23000_MIB')
if apps['exit_code'] or apps['stdout'].strip():issues.append('GPU_COMPUTE_OCCUPIED_OR_UNKNOWN')
disk=dict(zip(('total','used','free'),shutil.disk_usage('/root/rivermind-data')))
shm=dict(zip(('total','used','free'),shutil.disk_usage('/dev/shm')))
minimum=10*1024**3+7468230540+512*1024**2+2246400000+16*1024**2
if disk['free']<minimum:issues.append('STATIC_C0_LOWER_BOUND_AND_FLOOR_NOT_MET')
if shm['free']<64*1024**2:issues.append('RESIDUAL_SHM_ENVELOPE_NOT_MET')
manifest=pathlib.Path('/root/rivermind-data/DROID_W_TASK003_VAL007_OBSERVATION_R1/inputs/val_007_full_00001-00487/INPUT.json')
input_sha=sha(manifest)
if input_sha!=lock['input_manifest_sha256']:issues.append('INPUT_MANIFEST_MISMATCH')
python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'
versions=cmd([python,'-B','-c','import importlib.metadata,json;print(json.dumps({x:importlib.metadata.version(x) for x in ("torch","rerun-sdk","numpy")}))'])
if versions['exit_code']:issues.append('EXISTING_RUNTIME_METADATA_UNAVAILABLE')
cgroup={}
for name in ['memory.max','memory.current','memory.peak']:
 p=pathlib.Path('/sys/fs/cgroup')/name
 if p.exists():cgroup[name]=p.read_text().strip()
record={'hostname':socket.gethostname(),'endpoint':'sc01-ssh.gpuhome.cc:30448','origin':str(origin),
 'reviewed_commit':head,'tracked_status':status,'GPU':gpu,'compute_apps':apps,'disk':disk,'shm':shm,
 'cgroup':cgroup,'static_minimum_free_bytes':minimum,'complete_C0_size_known':False,
 'protected_pins':verified,'input_manifest_sha256':input_sha,'runtime':versions,
 'issues':issues,'preflight_passed':not issues,'model_initialized':False,'cuda_initialized':False,
 'GPU_UUID_must_match_historical':False,'approved_mode':'capture_only_stop_after_C0'}
print(json.dumps(record))
'''
d=json.loads(call('PREFLIGHT',code,timeout=180))
(ROOT/'evidence/C0_PREFLIGHT.json').write_text(json.dumps(d,indent=2))
print(json.dumps({k:v for k,v in d.items() if k not in ('protected_pins','runtime')}))
if not d['preflight_passed']:raise SystemExit(2)
