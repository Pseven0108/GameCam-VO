import sys,pathlib,json,shutil
from transport import *
code=r'''
import sys,pathlib,json,subprocess,shutil,os,socket,hashlib
s=json.loads(sys.stdin.readline());a=pathlib.Path(s['a']);lock=json.loads((a/'evidence/LOCKDOWN.json').read_text())
def cmd(v):
 p=subprocess.run(v,capture_output=True,text=True,timeout=20);assert p.returncode==0,p.stderr;return p.stdout.strip()
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
records=[]
for arm in ['E3','E4','E7','E0','E8','E6','E1','E2']:
 d=json.loads((a/'results'/arm/'COMPLETE.json').read_text());p=pathlib.Path(d['attempt']);files=[q for q in p.rglob('*') if q.is_file()]
 records.append(dict(arm=arm,attempt=str(p),raw_bytes=sum(q.stat().st_size for q in files),files=len(files),observer_bytes=(p/'observer.jsonl').stat().st_size,rerun=[dict(path=str(q),bytes=q.stat().st_size) for q in files if q.suffix=='.rrd'],zip_bytes=(a/'sealed_results'/(arm+'_'+p.name+'.zip')).stat().st_size))
source=pathlib.Path(lock['source']);pip=pathlib.Path(lock['pipeline']);views=[]
for f in ['tcp','tcp6']:
 for line in pathlib.Path('/proc/net',f).read_text().splitlines()[1:]:
  x=line.split()
  if x[3]=='0A' and int(x[1].split(':')[1],16) in [9875,9876,9877]:views.append(line)
seeds={}
for rel in ['run.py','src/utils/common.py']:
 text=(source/rel).read_text();lines=text.splitlines();chunks=[]
 for i,line in enumerate(lines):
  if 'def setup_seed' in line:chunks.append(dict(line=i+1,text='\n'.join(lines[i:i+18])))
 seeds[rel]=chunks
protected=[dict(path=p,expected=h,actual=sha(p),bytes=pathlib.Path(p).stat().st_size) for p,h in lock['pins'].items()]
print(json.dumps(dict(hostname=socket.gethostname(),gpu=cmd(['nvidia-smi','--query-gpu=name,uuid,memory.total,memory.free,memory.used','--format=csv,noheader,nounits']),gpu_processes=cmd(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits']),disk=shutil.disk_usage(a)._asdict(),shm=shutil.disk_usage('/dev/shm')._asdict(),records=records,seed_functions=seeds,source=lock['source'],pipeline=lock['pipeline'],pins=protected,rerun_listeners=views,lock=lock,cgroup_memory=pathlib.Path('/sys/fs/cgroup/memory.max').read_text().strip())))
'''
d=rpc(code,{'a':'/root/rivermind-data/'+A.name},'CURRENT_RESOURCE_AND_TASK004A_AUDIT',timeout=300)
d['local_disk']=shutil.disk_usage(ROOT)._asdict();put(ROOT/'evidence/PREFLIGHT_RAW.json',d)
raw=max(x['raw_bytes'] for x in d['records']);z=max(x['zip_bytes'] for x in d['records']);logs=256*1024**2;budget=16*(raw+z+logs)+raw+z+10*1024**3
localneed=16*(raw+z)+10*1024**3
status=dict(remote_free=d['disk']['free'],max_task004a_raw=raw,max_task004a_zip=z,additional_log_and_recording_allowance_per_run=logs,archive_temporary_allowance=raw+z,total_remote_required=budget,local_required=localneed,local_free=d['local_disk']['free'],all_remote_outputs_and_archives_retained=True,remote_ready=d['disk']['free']>=budget,local_ready=d['local_disk']['free']>=localneed,protected_matches=sum(x['expected']==x['actual'] for x in d['pins']),protected_count=len(d['pins']))
put(ROOT/'evidence/STORAGE_PREFLIGHT.json',status)
print(json.dumps(dict(storage=status,hostname=d['hostname'],gpu=d['gpu'],gpu_processes=d['gpu_processes'],shm=d['shm'],seed_functions=d['seed_functions'],listeners=d['rerun_listeners']),ensure_ascii=False))
assert status['remote_ready'] and status['local_ready'],'STORAGE_BLOCKED'
assert status['protected_matches']==status['protected_count'],'FROZEN_FILE_DRIFT'
assert not d['gpu_processes'],'GPU_ALREADY_IN_USE'
assert not d['rerun_listeners'],'RERUN_PORT_CONFLICT'
