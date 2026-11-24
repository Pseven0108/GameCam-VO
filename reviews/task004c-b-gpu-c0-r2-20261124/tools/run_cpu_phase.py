import base64,io,json,zipfile
from remote_cpu import ROOT,call
payload={'test_b64':base64.b64encode((ROOT/'tools/real_loader_tests.py').read_bytes()).decode(),
 'protocol_b64':base64.b64encode((ROOT/'evidence/APPROVED_47_FAMILY_PROTOCOL.json').read_bytes()).decode()}
code=r'''
import base64,io,json,os,pathlib,shutil,subprocess,sys,zipfile
p=json.load(sys.stdin);root=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_GPU_C0_R2_20261124_R1')
tests=root/'tests';assert tests.is_symlink();tests.unlink();shutil.copytree(root/'source_candidate/tests',tests)
(root/'cpu_tests/real_loader_tests.py').write_bytes(base64.b64decode(p['test_b64']))
(root/'evidence/APPROVED_47_FAMILY_PROTOCOL.json').write_bytes(base64.b64decode(p['protocol_b64']))
python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='43',
 PYTHONPATH=str(root)+':'+str(root/'source_candidate'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
results=[]
for name,args in [('REAL_LOADER',[str(root/'cpu_tests/real_loader_tests.py')]),('ORIGINAL_152',[str(root/'tests/run_release_cpu_tests.py'),'c0_r2'])]:
 q=subprocess.run([python,'-B','-u',*args],cwd=root,env=env,capture_output=True,text=True,timeout=240)
 row={'name':name,'exit_code':q.returncode,'stdout':q.stdout,'stderr':q.stderr};results.append(row)
 (root/'artifacts'/(name+'_PROCESS_RESULT.json')).write_text(json.dumps(row,indent=2))
 if q.returncode:break
passed=len(results)==2 and all(r['exit_code']==0 for r in results)
(root/'evidence/CPU_PHASE_DECISION.json').write_text(json.dumps({'CPU_passed':passed,'GPU_started':False,'results':results},indent=2))
memory=io.BytesIO()
with zipfile.ZipFile(memory,'w',zipfile.ZIP_DEFLATED) as z:
 for base in [root/'artifacts/REAL_LOADER_CPU',root/'artifacts/RELEASE_CPU_c0_r2']:
  if base.exists():
   for f in base.rglob('*'):
    if f.is_file():z.write(f,f.relative_to(root).as_posix())
 for f in list((root/'evidence').glob('*'))+list((root/'artifacts').glob('*PROCESS_RESULT.json')):
  if f.is_file():z.write(f,f.relative_to(root).as_posix())
print(json.dumps({'CPU_passed':passed,'results':results,'artifacts_b64':base64.b64encode(memory.getvalue()).decode()}))
'''
d=json.loads(call('REAL_LOADER_AND_152_CPU',code,input_bytes=json.dumps(payload).encode(),timeout=420,
 python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'))
raw=base64.b64decode(d.pop('artifacts_b64'))
with zipfile.ZipFile(io.BytesIO(raw)) as z:
 assert z.testzip() is None
 dest=ROOT/'CPU_evidence';dest.mkdir(exist_ok=False);z.extractall(dest)
(ROOT/'evidence/CPU_PHASE_DECISION.json').write_text(json.dumps(d,indent=2))
print(json.dumps(d))
if not d['CPU_passed']:raise SystemExit(2)
