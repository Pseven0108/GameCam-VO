"""Log a CPU program's actual stdout/stderr/exit status without importing it."""
import os,sys,pathlib,json,subprocess,time,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
script=pathlib.Path(sys.argv[1]).resolve();label=sys.argv[2]
if not script.is_relative_to(ROOT):raise ValueError('Only new TASK005B scripts allowed')
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
dest=ROOT/'04_tests';start=time.time()
with (dest/(label+'.stdout.txt')).open('xb') as out,(dest/(label+'.stderr.txt')).open('xb') as err:
    p=subprocess.run([sys.executable,'-B',str(script)],env=env,stdout=out,stderr=err)
receipt={'script':str(script.relative_to(ROOT)),'script_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),'start_unix':start,'end_unix':time.time(),'exit_code':p.returncode,'CUDA_VISIBLE_DEVICES':'','stdout_sha256':hashlib.sha256((dest/(label+'.stdout.txt')).read_bytes()).hexdigest(),'stderr_sha256':hashlib.sha256((dest/(label+'.stderr.txt')).read_bytes()).hexdigest()}
(dest/(label+'.receipt.json')).write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt));sys.exit(p.returncode)
