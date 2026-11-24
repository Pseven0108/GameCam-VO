"""Rerun only CPU evaluation after a NumPy scalar JSON serialization repair."""
import hashlib,json,os,pathlib,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
PY=r'C:\Program Files\WindowsApps\OpenAI.CodexPrimaryRuntime.v26-1123-915-0_26.1123.915.0_x64__3k8sg7r9htsxt\dependencies\python\python.exe'
base=ROOT/'evidence/R3_FINAL_CPU_OFFLINE_EVALUATION_02'
out=base.with_suffix('.stdout.txt');err=base.with_suffix('.stderr.txt');receipt=base.with_suffix('.receipt.json')
assert not any(p.exists() for p in (out,err,receipt))
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
start=time.time()
with out.open('xb') as of,err.open('xb') as ef:q=subprocess.run([PY,'-B',str(ROOT/'analysis/offline_crossover_r3.py')],cwd=ROOT,env=env,stdout=of,stderr=ef,timeout=600)
r={'CPU_only':True,'start_unix':start,'end_unix':time.time(),'exit_code':q.returncode,'script_sha256':hashlib.sha256((ROOT/'analysis/offline_crossover_r3.py').read_bytes()).hexdigest(),'stdout_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'stderr_sha256':hashlib.sha256(err.read_bytes()).hexdigest(),'repair':'Convert NumPy scalar to equivalent Python scalar for strict JSON only; geometry and metric formulas unchanged','model_reruns':0,'failed_evaluation_preserved':'analysis_failures/R3_FINAL_CPU_OFFLINE_EVALUATION_01'}
receipt.write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
if q.returncode:raise RuntimeError(err.read_text(encoding='utf-8',errors='replace')[-3000:])
