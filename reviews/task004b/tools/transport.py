import pathlib,sys,json,subprocess,base64,shlex,hashlib,os,time,shutil
from datetime import datetime,timezone
ROOT=pathlib.Path(__file__).resolve().parents[1]
A=pathlib.Path("D:/aaa/GameCam-VO/experiments/DROID_W_TASK004A_GPU_SCREENING_20261123T082038066Z")
sys.path.insert(0,str(A/'bootstrap'))
from run_once import ssh_base,HOST,CREATE,verified
PRE=json.loads((A/'bootstrap/evidence/preflight.json').read_text())
REMOTE='/root/rivermind-data/'+ROOT.name
UTC=lambda:datetime.now(timezone.utc).isoformat()
def put(p,d):
 with pathlib.Path(p).open('x',encoding='utf-8') as f:json.dump(d,f,indent=2,ensure_ascii=False,allow_nan=False)
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def rpc(code,payload,name,timeout=240):
 loader="import sys,base64;exec(compile(base64.b64decode(sys.stdin.readline()),'<task004b-cpu-control>','exec'))"
 cmd='exec env CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /usr/bin/python3 -I -B -u -c '+shlex.quote(loader)
 data=base64.b64encode(code.encode())+b'\n'+json.dumps(payload).encode()+b'\n'
 p=subprocess.run(ssh_base(PRE)+['-o','ClearAllForwardings=yes',HOST,cmd],input=data,capture_output=True,creationflags=CREATE,timeout=timeout)
 err=ROOT/'evidence'/f'{name}.ssh.stderr.txt';err.write_bytes(p.stderr);(ROOT/'evidence'/f'{name}.stdout.txt').write_bytes(p.stdout)
 trust=verified(err);put(ROOT/'evidence'/f'{name}.transport.json',dict(exit_code=p.returncode,trust=trust,utc=UTC()))
 assert all(trust.values()),'SSH trust verification failed'
 assert p.returncode==0,(name,p.returncode,p.stderr.decode(errors='replace')[-1800:],p.stdout.decode(errors='replace')[-2000:])
 return json.loads(p.stdout)
