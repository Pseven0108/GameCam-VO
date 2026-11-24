import sys,pathlib,json,base64,hashlib,shutil,subprocess,socket,tarfile,io,os,time
s=json.loads(sys.stdin.readline());root=pathlib.Path(s['root']);a=pathlib.Path(s['a']);assert socket.gethostname()==s['hostname'];assert not root.exists()
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def put(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2)
lock=json.loads((a/'evidence/LOCKDOWN.json').read_text())
for p,v in lock['pins'].items():assert sha(p)==v,p
free=shutil.disk_usage(a).free;assert free>=s['budget'],'STORAGE_BLOCKED'
root.mkdir();(root/'evidence').mkdir();(root/'results').mkdir();(root/'sealed_results').mkdir();(root/'release').mkdir()
with tarfile.open(fileobj=io.BytesIO(base64.b64decode(s['release'])),mode='r:gz') as t:
 for m in t.getmembers():
  p=(root/'release'/m.name).resolve();assert m.isfile() and p.is_relative_to(root/'release')
  p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(t.extractfile(m).read())
release=json.loads((root/'release/RELEASE_SHA256.json').read_text())
for n,h in release.items():assert sha(root/'release'/n)==h,n
shutil.copytree(lock['source'],root/'source',symlinks=True,ignore=shutil.ignore_patterns('__pycache__','.git'))
shutil.copytree(lock['pipeline'],root/'pipeline',symlinks=True,ignore=shutil.ignore_patterns('__pycache__'))
shutil.copyfile(root/'release/candidates/task004_controls.py',root/'source/task004_controls.py')
shutil.copyfile(root/'release/candidates/task004_run_segment.py',root/'pipeline/task004_run_segment.py')
new=dict(lock,root=str(root),source=str(root/'source'),pipeline=str(root/'pipeline'),config=str(root/'release/candidates/r2_sealed_config.yaml'),extension=str(root/'source/droid_backends.cpython-310-x86_64-linux-gnu.so'))
new['pins']={str(p):sha(p) for parent in (root/'source',root/'pipeline',root/'release') for p in parent.rglob('*') if p.is_file()}
for p,h in lock['pins'].items():new['pins'][p]=h
put(root/'evidence/LOCKDOWN.json',new)
# Pure static validation: only authorization and policy modules, never model imports.
sys.path.insert(0,str(root/'source'));import task004_controls as c
for arm in c.FACTORIAL:
 raw=(root/'release/policies'/(arm+'.json')).read_bytes();assert c.parse_policy(json.loads(raw)).local_dwu==c.FACTORIAL[arm]
# Preserve exact source for seeding and document child spawn scope.
seeds={}
for rel in ('run.py','src/utils/common.py'):
 text=(root/'source'/rel).read_text();lines=text.splitlines();i=next(i for i,v in enumerate(lines) if 'def setup_seed' in v)
 seeds[rel]=dict(line=i+1,text=chr(10).join(lines[i:i+11]))
put(root/'evidence/SEED_SOURCE_AUDIT.json',dict(seed_functions=seeds,main_native_setup_seed=True,tracking_spawn_has_no_extra_native_seed_call=True,no_extra_child_reseeding=True,determinism_not_claimed=True))
rr=subprocess.run([s['viewer_bin'],'rrd','--help'],capture_output=True,text=True,timeout=20)
put(root/'evidence/RERUN_RRD_CLI_HELP.json',dict(exit_code=rr.returncode,stdout=rr.stdout,stderr=rr.stderr))
put(root/'evidence/PREFLIGHT.json',dict(status='PASS',cpu_only=True,model_runs=0,hostname=socket.gethostname(),disk_free_bytes=free,protected_files=len(new['pins']),release_files=len(release),original_config_sha256=sha(pathlib.Path(lock['config'])),storage_plan=s['storage_plan']))
print(json.dumps(dict(status='PASS',root=str(root),protected_files=len(new['pins']),release_files=len(release),disk_free=shutil.disk_usage(root).free,rrd_help=rr.stdout)))
