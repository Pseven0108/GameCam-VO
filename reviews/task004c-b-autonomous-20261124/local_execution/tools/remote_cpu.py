"""Pinned SSH transport for the single C0 task; no connection at import."""
import base64,hashlib,importlib.util,json,pathlib,shlex,subprocess
from datetime import datetime,timezone
ROOT=pathlib.Path(__file__).resolve().parents[1]
BOOT=pathlib.Path(r'D:\aaa\GameCam-VO\experiments\DROID_W_TASK004A_GPU_SCREENING_20261123T082038066Z\bootstrap')
spec=importlib.util.spec_from_file_location('trusted_ssh',BOOT/'run_once.py')
ssh=importlib.util.module_from_spec(spec);spec.loader.exec_module(ssh)
pre=json.loads((BOOT/'evidence/preflight.json').read_text())
def base():
 b=ssh.ssh_base(pre);b[b.index('-p')+1]='REDACTED_SSH_PORT';return b
def call(label,code,*,input_bytes=None,timeout=180,python='/usr/bin/python3'):
 (ROOT/'logs').mkdir(exist_ok=True);(ROOT/'evidence').mkdir(exist_ok=True)
 stdout=ROOT/'logs'/(label+'.stdout.txt');stderr=ROOT/'logs'/(label+'.stderr.txt')
 loader='import base64;exec(compile(base64.b64decode('+repr(base64.b64encode(code.encode()).decode())+'),"<C0-task>","exec"))'
 cmd='exec env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 '+shlex.quote(python)+' -B -u -c '+shlex.quote(loader)
 start=datetime.now(timezone.utc).isoformat()
 with stdout.open('xb') as of,stderr.open('xb') as ef:
  p=subprocess.run(base()+['-o','ClearAllForwardings=yes',ssh.HOST,cmd],input=input_bytes,
       stdout=of,stderr=ef,timeout=timeout,creationflags=ssh.CREATE)
 receipt={'label':label,'endpoint':'REDACTED_SSH_HOST:REDACTED_SSH_PORT','start_UTC':start,
          'end_UTC':datetime.now(timezone.utc).isoformat(),'ssh_exit_code':p.returncode,
          'trust':ssh.verified(stderr),'code_sha256':hashlib.sha256(code.encode()).hexdigest()}
 (ROOT/'evidence'/(label+'_TRANSPORT.json')).write_text(json.dumps(receipt,indent=2))
 if p.returncode or not all(receipt['trust'].values()):raise RuntimeError(receipt)
 return stdout.read_text('utf-8')
