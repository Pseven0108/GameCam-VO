import base64,hashlib,io,json,pathlib,zipfile
from remote_access import ROOT,run
REMOTE='/root/rivermind-data/DROID_W_TASK004C_B_NATIVE_RELEASE_FIXES_20261124_R1'
code=r'''
import os
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1'
import base64,hashlib,io,json,pathlib,subprocess,sys,zipfile
root=pathlib.Path(REMOTE_ROOT);script=root/'tools/full_buffer_stress.py';script.write_bytes(sys.stdin.buffer.read())
q=subprocess.run([sys.executable,'-B',str(script)],cwd=root,capture_output=True,timeout=300,
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONPATH=str(root)+':'+str(root/'source_candidate'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2'))
(root/'logs/FULL_BUFFER.stdout.txt').write_bytes(q.stdout);(root/'logs/FULL_BUFFER.stderr.txt').write_bytes(q.stderr)
result={'exit_code':q.returncode,'stdout':q.stdout.decode(errors='replace'),'stderr':q.stderr.decode(errors='replace')}
b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
 for p in (root/'artifacts/FULL_BUFFER_CPU_PROOF').rglob('*.json'):z.write(p,p.relative_to(root).as_posix())
result['evidence_b64']=base64.b64encode(b.getvalue()).decode();print(json.dumps(result))
'''.replace('REMOTE_ROOT',repr(REMOTE))
r=json.loads(run('FULL_BUFFER_CPU_PROOF',code,python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python',timeout=330,input_bytes=(ROOT/'tools/full_buffer_stress.py').read_bytes()))
raw=base64.b64decode(r.pop('evidence_b64'));target=ROOT/'evidence/FULL_BUFFER';target.mkdir(exist_ok=False)
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    assert z.testzip() is None
    for n in z.namelist():
        p=target/n;assert p.resolve().is_relative_to(target.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(n))
(ROOT/'evidence/FULL_BUFFER_RESULT.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
if r['exit_code']:raise SystemExit(1)
