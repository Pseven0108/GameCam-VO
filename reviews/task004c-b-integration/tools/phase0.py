import json, pathlib
from remote_access import ROOT, run

lock=json.loads((ROOT/'configs/identity_lock.json').read_text())
code=r'''
import base64, hashlib, io, json, os, pathlib, shutil, socket, subprocess, time, zipfile
LOCK=LOCK_PLACEHOLDER
source=pathlib.Path('/root/rivermind-data/DROID_W_TASK004B_CONFIRMATORY_20261123T124144277Z/source')
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
def cmd(args):
 try:
  q=subprocess.run(args,capture_output=True,text=True,timeout=15)
  return {'args':args,'exit_code':q.returncode,'stdout':q.stdout,'stderr':q.stderr}
 except Exception as e:return {'args':args,'exit_code':None,'error':repr(e)}
r={'hostname':socket.gethostname(),'timestamp':time.time(),'source':str(source),'cuda_initialized':False,'models_loaded':False}
assert r['hostname']=='jupyter-yd6gks8uzfbxzdb4','Unexpected container'
r['disk']={n:dict(zip(('total','used','free'),shutil.disk_usage(p))) for n,p in [('data','/root/rivermind-data'),('shm','/dev/shm'),('system','/opt')]}
r['gpu']=cmd(['nvidia-smi','--query-gpu=name,memory.total,memory.free,driver_version','--format=csv,noheader,nounits'])
r['compute_apps']=cmd(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits']) if r['gpu'].get('exit_code')==0 else {'not_run':'GPU_TOOL_FAILED'}
r['pins']={}
for p,expected in {**LOCK['remote_pins'],**LOCK['execution_source_pins']}.items():
 f=pathlib.Path(p); actual=sha(f) if f.is_file() else None
 r['pins'][p]={'expected':expected,'actual':actual,'match':actual==expected,'bytes':f.stat().st_size if f.is_file() else None}
r['git']=cmd(['git','-C',str(source),'status','--porcelain=v1','-uno'])
r['source_manifest']=[]
b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(source.rglob('*')):
  if '.git' in p.parts or '__pycache__' in p.parts:continue
  rel=p.relative_to(source).as_posix()
  if p.is_symlink():
   r['source_manifest'].append({'path':rel,'kind':'symlink','target':os.readlink(p)})
  elif p.is_file():
   s=p.stat(); row={'path':rel,'kind':'file','bytes':s.st_size,'sha256':sha(p)};r['source_manifest'].append(row)
   if p.suffix in ('.py','.cu','.cpp','.c','.h','.hpp','.yaml','.yml','.json','.md','.txt') and s.st_size<3*1024**2:
    z.write(p,rel)
r['source_text_archive_b64']=base64.b64encode(b.getvalue()).decode()
r['processes']=cmd(['ps','-eo','pid,ppid,comm'])
print(json.dumps(r))
'''.replace('LOCK_PLACEHOLDER',repr(lock))
data=json.loads(run('PHASE0',code,timeout=240))
archive=__import__('base64').b64decode(data.pop('source_text_archive_b64'))
(ROOT/'evidence/SOURCE_EXECUTION_BEFORE.zip').write_bytes(archive)
import io, zipfile
with zipfile.ZipFile(io.BytesIO(archive)) as z:
 assert z.testzip() is None
 for n in z.namelist():
  p=ROOT/'source_before'/n
  assert p.resolve().is_relative_to((ROOT/'source_before').resolve())
  p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(n))
(ROOT/'evidence/PHASE0.json').write_text(json.dumps(data,indent=2))
print(json.dumps({k:data[k] for k in ('hostname','disk','gpu','compute_apps')},indent=2))
print('pins',sum(x['match'] for x in data['pins'].values()),'/',len(data['pins']))
print('source_files',len(data['source_manifest']))
assert all(x['match'] for x in data['pins'].values()),'Protected source or model mismatch'
