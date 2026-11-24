"""Deploy only an independent candidate, retain every test receipt."""
import base64,hashlib,io,json,pathlib,sys,zipfile
from remote_access import ROOT,run
REMOTE='/root/rivermind-data/DROID_W_TASK004C_B_NATIVE_INTEGRATION_20261124_R1'
LABEL=sys.argv[1] if len(sys.argv)>1 else 'initial'
members={};b=io.BytesIO()
paths=[ROOT/'control_common.py']
for folder in ('checkpoint','schedule','runner','configs','tests','native_control'):
    paths += [p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
changed=json.loads((ROOT/'evidence/PATCHED_FILES.json').read_text())
paths += [ROOT/'source_candidate'/n for n in changed]
paths += [ROOT/'source_before'/n for n in changed]
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(set(paths)):
        n=p.relative_to(ROOT).as_posix();raw=p.read_bytes();members[n]=hashlib.sha256(raw).hexdigest();z.writestr(n,raw)
    z.writestr('UPLOAD_SHA.json',json.dumps(members))
    z.writestr('BASELINE_FULL_MANIFEST.json',json.dumps(json.loads((ROOT/'evidence/PHASE0.json').read_text())['source_manifest']))
raw=b.getvalue();(ROOT/'artifacts'/('CANDIDATE_UPLOAD_'+LABEL+'.zip')).write_bytes(raw)
code=r'''
import os
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1'
import base64,hashlib,io,json,pathlib,shutil,socket,subprocess,sys,zipfile
root=pathlib.Path(REMOTE_PLACEHOLDER);label=LABEL_PLACEHOLDER
assert socket.gethostname()=='jupyter-yd6gks8uzfbxzdb4'
raw=sys.stdin.buffer.read();assert hashlib.sha256(raw).hexdigest()==UPLOAD_SHA_PLACEHOLDER
if shutil.disk_usage('/root/rivermind-data').free<10*1024**3+256*1024**2:raise RuntimeError('STORAGE_BLOCKED')
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for x in iter(lambda:f.read(8*1024**2),b''):h.update(x)
 return h.hexdigest()
def git(*a):
 q=subprocess.run(['git','-C',str(root/'source_candidate'),'-c','user.name=GameCam Native Integration','-c','user.email=gamecam@localhost',*a],capture_output=True,text=True,check=True);return q.stdout.strip()
with zipfile.ZipFile(io.BytesIO(raw)) as z:
 assert z.testzip() is None
 pins=json.loads(z.read('UPLOAD_SHA.json'));baseline=json.loads(z.read('BASELINE_FULL_MANIFEST.json'))
 if label=='initial':
  root.mkdir(exist_ok=False)
  source=pathlib.Path('/root/rivermind-data/DROID_W_TASK004B_CONFIRMATORY_20261123T124144277Z/source')
  shutil.copytree(source,root/'source_candidate',symlinks=True,ignore=shutil.ignore_patterns('.git','__pycache__'))
  verified=[]
  for row in baseline:
   p=root/'source_candidate'/row['path']
   assert (p.is_symlink() and os.readlink(p)==row['target']) if row['kind']=='symlink' else (p.is_file() and p.stat().st_size==row['bytes'] and sha(p)==row['sha256']),row['path']
   verified.append(row['path'])
  (root/'BASELINE_COPY_VERIFICATION.json').write_text(json.dumps({'verified_count':len(verified),'copied_file_bytes':sum(x.get('bytes',0) for x in baseline),'original_source_written':False}))
  git('init','--initial-branch=codex/task004c-b-native-integration')
  git('add','--force','--all');git('commit','-m','Freeze full execution source copy before native control changes')
  (root/'BASELINE_GIT_COMMIT.txt').write_text(git('rev-parse','HEAD'))
 else:
  assert root.is_dir() and (root/'BASELINE_GIT_COMMIT.txt').is_file()
 for n,pin in pins.items():
  p=root/n
  if not p.resolve().is_relative_to(root.resolve()):raise RuntimeError('Unsafe candidate member')
  value=z.read(n);assert hashlib.sha256(value).hexdigest()==pin
  p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value)
 (root/('UPLOAD_SHA_'+label+'.json')).write_text(json.dumps(pins,indent=2))
 # Keep the control implementation inside the candidate Git history as well.
 for name in ['native_control','checkpoint','schedule','runner']:
  target=root/'source_candidate'/name
  if target.exists():
   for p in (root/name).rglob('*.py'):
    d=target/p.relative_to(root/name);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d)
  else:shutil.copytree(root/name,target,ignore=shutil.ignore_patterns('__pycache__'))
 shutil.copy2(root/'control_common.py',root/'source_candidate/control_common.py')
 git('add','--all');git('commit','--allow-empty','-m','Native control CPU interface revision '+label)
commit=git('rev-parse','HEAD')
(root/'artifacts').mkdir(exist_ok=True)
q=subprocess.run([sys.executable,'-B',str(root/'tests/run_native_cpu_tests.py'),label],cwd=root,capture_output=True,timeout=300,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2'))
(root/'artifacts'/('CPU_'+label+'.stdout.txt')).write_bytes(q.stdout);(root/'artifacts'/('CPU_'+label+'.stderr.txt')).write_bytes(q.stderr)
b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
 for p in (root/'artifacts').rglob('*'):
  if p.is_file():z.write(p,p.relative_to(root).as_posix())
 for name in ['BASELINE_COPY_VERIFICATION.json','BASELINE_GIT_COMMIT.txt']:z.write(root/name,name)
print(json.dumps({'root':str(root),'candidate_git_commit':commit,'cpu_exit_code':q.returncode,'stdout':q.stdout.decode(errors='replace'),'stderr':q.stderr.decode(errors='replace'),'free_bytes_after':shutil.disk_usage(root).free,'results_zip_b64':base64.b64encode(b.getvalue()).decode()}))
'''.replace('REMOTE_PLACEHOLDER',repr(REMOTE)).replace('LABEL_PLACEHOLDER',repr(LABEL)).replace('UPLOAD_SHA_PLACEHOLDER',repr(hashlib.sha256(raw).hexdigest()))
result=json.loads(run('DEPLOY_CPU_'+LABEL,code,timeout=360,python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python',input_bytes=raw))
payload=base64.b64decode(result.pop('results_zip_b64'))
target=ROOT/'evidence'/('CPU_'+LABEL);target.mkdir(exist_ok=False);(target/'REMOTE_RESULTS.zip').write_bytes(payload)
with zipfile.ZipFile(io.BytesIO(payload)) as z:
    assert z.testzip() is None
    for n in z.namelist():
        p=target/n;assert p.resolve().is_relative_to(target.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(n))
(ROOT/'evidence'/('CPU_'+LABEL+'_RECEIPT.json')).write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
if result['cpu_exit_code']:raise SystemExit(1)
