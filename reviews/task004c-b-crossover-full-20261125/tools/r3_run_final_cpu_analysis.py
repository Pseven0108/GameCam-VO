"""Execute final CPU-only evidence audit and offline evaluation with full receipts."""
import hashlib,json,os,pathlib,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
PY=pathlib.Path(r'C:\Program Files\WindowsApps\OpenAI.CodexPrimaryRuntime.v26-1123-915-0_26.1123.915.0_x64__3k8sg7r9htsxt\dependencies\python\python.exe')
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
for step,script in [('CONTROL_AUDIT','audit_completed_stages_r3.py'),('OFFLINE_EVALUATION','offline_crossover_r3.py')]:
 base=ROOT/'evidence'/('R3_FINAL_CPU_'+step)
 out=base.with_suffix('.stdout.txt');err=base.with_suffix('.stderr.txt');receipt=base.with_suffix('.receipt.json')
 assert not any(p.exists() for p in (out,err,receipt))
 start=time.time()
 with out.open('xb') as of,err.open('xb') as ef:
  q=subprocess.run([str(PY),'-B',str(ROOT/'analysis'/script)],env=env,cwd=ROOT,stdout=of,stderr=ef,timeout=600)
 r={'step':step,'script':'analysis/'+script,'script_sha256':hashlib.sha256((ROOT/'analysis'/script).read_bytes()).hexdigest(),'start_unix':start,'end_unix':time.time(),'exit_code':q.returncode,'stdout_path':out.relative_to(ROOT).as_posix(),'stdout_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'stderr_path':err.relative_to(ROOT).as_posix(),'stderr_sha256':hashlib.sha256(err.read_bytes()).hexdigest(),'CUDA_VISIBLE_DEVICES':'','model_runs_started':0}
 receipt.write_text(json.dumps(r,indent=2))
 print(json.dumps(r),flush=True)
 if q.returncode:raise RuntimeError(err.read_text(encoding='utf-8',errors='replace')[-3000:])
print('Final CPU audit and offline evaluation completed.',flush=True)
