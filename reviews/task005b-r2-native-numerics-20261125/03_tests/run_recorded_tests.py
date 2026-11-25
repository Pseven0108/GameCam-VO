import sys,pathlib,subprocess,json,time,os,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
out=ROOT/'03_tests/recorded';out.mkdir(exist_ok=False)
rows=[]
for name in ['test_observer_contract.py','test_evidence_integrity.py']:
 start=time.time();p=subprocess.run([sys.executable,'-B',str(ROOT/'03_tests'/name)],capture_output=True,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''))
 for suffix,b in [('stdout',p.stdout),('stderr',p.stderr)]:
  (out/(name+'.'+suffix+'.txt')).write_bytes(b)
 proof={'script':name,'script_sha256':hashlib.sha256((ROOT/'03_tests'/name).read_bytes()).hexdigest(),'exit_code':p.returncode,'seconds':time.time()-start,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),'CUDA_VISIBLE_DEVICES':''}
 rows.append(proof);assert p.returncode==0,proof
(out/'RECORDED_TESTS.json').write_text(json.dumps({'PASS':True,'tests':16,'groups':rows},indent=2)+'\n')
print(json.dumps({'PASS':True,'tests':16,'groups':len(rows)}))
