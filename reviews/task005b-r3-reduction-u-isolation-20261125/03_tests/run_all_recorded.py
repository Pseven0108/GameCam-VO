import pathlib,subprocess,sys,json,hashlib,os,time
ROOT=pathlib.Path(__file__).resolve().parents[1];out=ROOT/'03_tests/recorded_full';out.mkdir(exist_ok=False)
env=dict(os.environ,CUDA_VISIBLE_DEVICES='');reports=[]
for name,n in [('test_source_contract.py',14),('test_numerics.py',8),('test_evidence.py',8)]:
    start=time.time();prefix=out/name.replace('.py','')
    with pathlib.Path(str(prefix)+'.stdout.txt').open('xb') as fo,pathlib.Path(str(prefix)+'.stderr.txt').open('xb') as fe:
        p=subprocess.run([sys.executable,'-B',str(ROOT/'03_tests'/name)],stdout=fo,stderr=fe,env=env)
    reports.append({'name':name,'tests':n,'exit_code':p.returncode,'seconds':time.time()-start})
    assert p.returncode==0,reports
proof={'PASS':True,'tests':sum(r['tests'] for r in reports),'suites':reports,'logs_SHA':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}}
(ROOT/'03_tests/FULL_CPU_TEST_REPORT.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
