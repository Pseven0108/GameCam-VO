import pathlib,subprocess,sys,json,hashlib,os,time
ROOT=pathlib.Path(__file__).resolve().parents[1];out=ROOT/'03_tests/recorded';out.mkdir(exist_ok=False)
env=dict(os.environ,CUDA_VISIBLE_DEVICES='');start=time.time()
with (out/'stdout.txt').open('xb') as fo,(out/'stderr.txt').open('xb') as fe:
    p=subprocess.run([sys.executable,'-B',str(ROOT/'03_tests/test_source_contract.py')],stdout=fo,stderr=fe,env=env)
proof={'PASS':p.returncode==0,'exit_code':p.returncode,'tests':14,'seconds':time.time()-start,'logs':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}}
(ROOT/'03_tests/CPU_TEST_REPORT.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2));assert proof['PASS']
