import base64,hashlib,io,json,pathlib,sys,zipfile
from remote_access import ROOT,run
LABEL=sys.argv[1] if len(sys.argv)>1 else 'initial'
REMOTE='/root/rivermind-data/DROID_W_TASK004C_B_NATIVE_RELEASE_FIXES_20261124_R1'
b=io.BytesIO();pins={}
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
    for base in ('candidate','tests'):
        for p in sorted((ROOT/base).rglob('*')):
            if p.is_file() and p.suffix=='.py' and '__pycache__' not in p.parts:
                n=p.relative_to(ROOT).as_posix();raw=p.read_bytes();pins[n]=hashlib.sha256(raw).hexdigest();z.writestr(n,raw)
    z.writestr('UPLOAD_SHA.json',json.dumps(pins))
raw=b.getvalue();(ROOT/'artifacts'/('UPLOAD_'+LABEL+'.zip')).write_bytes(raw)
code=r'''
import os
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1'
import base64,hashlib,io,json,pathlib,subprocess,sys,zipfile
root=pathlib.Path(REMOTE_ROOT);label=REVISION;raw=sys.stdin.buffer.read()
assert hashlib.sha256(raw).hexdigest()==EXPECTED
with zipfile.ZipFile(io.BytesIO(raw)) as z:
 assert z.testzip() is None
 pins=json.loads(z.read('UPLOAD_SHA.json'))
 for n,pin in pins.items():
  raw_file=z.read(n);assert hashlib.sha256(raw_file).hexdigest()==pin
  dest=root/('source_candidate/'+n[len('candidate/'):] if n.startswith('candidate/') else n)
  assert dest.resolve().is_relative_to(root.resolve())
  dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw_file)
 (root/'evidence'/('UPLOAD_SHA_'+label+'.json')).write_text(json.dumps(pins,indent=2))
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONPATH=str(root)+':'+str(root/'source_candidate'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
q=subprocess.run([sys.executable,'-B',str(root/'tests/run_release_cpu_tests.py'),label],cwd=root,env=env,capture_output=True,timeout=360)
(root/'logs'/('CPU_'+label+'.stdout.txt')).write_bytes(q.stdout);(root/'logs'/('CPU_'+label+'.stderr.txt')).write_bytes(q.stderr)
result={'exit_code':q.returncode,'stdout':q.stdout.decode(errors='replace'),'stderr':q.stderr.decode(errors='replace'),'label':label}
b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
 for p in (root/'artifacts'/('RELEASE_CPU_'+label)).rglob('*'):
  if p.is_file():z.write(p,p.relative_to(root).as_posix())
result['archive_b64']=base64.b64encode(b.getvalue()).decode();print(json.dumps(result))
'''.replace('REMOTE_ROOT',repr(REMOTE)).replace('REVISION',repr(LABEL)).replace('EXPECTED',repr(hashlib.sha256(raw).hexdigest()))
r=json.loads(run('CPU_'+LABEL,code,python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python',timeout=390,input_bytes=raw))
archive=base64.b64decode(r.pop('archive_b64'));target=ROOT/'evidence'/('CPU_'+LABEL);target.mkdir(exist_ok=False)
with zipfile.ZipFile(io.BytesIO(archive)) as z:
    assert z.testzip() is None
    for n in z.namelist():
        dest=target/n;assert dest.resolve().is_relative_to(target.resolve());dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(n))
(ROOT/'evidence'/('CPU_'+LABEL+'_RESULT.json')).write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
if r['exit_code']:raise SystemExit(1)
