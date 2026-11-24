import os,sys,json,pathlib,subprocess,base64,shlex,time,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
A=pathlib.Path(r'D:/aaa/GameCam-VO/experiments/DROID_W_TASK004A_GPU_SCREENING_20261123T082038066Z')
sys.path.insert(0,str(A/'bootstrap'))
from run_once import ssh_base,HOST,CREATE,verified
PRE=json.loads((A/'bootstrap/evidence/preflight.json').read_text(encoding='utf-8'))
AUTH=json.loads((ROOT/'AUTHORIZATION.json').read_text(encoding='utf-8'))
def remote(code,payload,tag,timeout=60,python='/usr/bin/python3',env=None):
    loader="import sys,base64;exec(compile(base64.b64decode(sys.stdin.readline()),'<task004c-recovery>','exec'))"
    e={'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
    if env:e.update(env)
    cmd='exec env '+' '.join(shlex.quote(k+'='+v) for k,v in e.items())+' '+shlex.quote(python)+' -I -B -u -c '+shlex.quote(loader)
    start=time.time()
    q=subprocess.run(ssh_base(PRE)+['-o','ClearAllForwardings=yes',HOST,cmd],input=base64.b64encode(code.encode())+b'\n'+json.dumps(payload).encode()+b'\n',capture_output=True,creationflags=CREATE,timeout=timeout)
    out=ROOT/'evidence'/f'{tag}.stdout.txt';err=ROOT/'evidence'/f'{tag}.ssh.stderr.txt'
    out.write_bytes(q.stdout);err.write_bytes(q.stderr)
    tr=verified(err)
    (ROOT/'evidence'/f'{tag}.process.json').write_text(json.dumps(dict(exit_code=q.returncode,elapsed_seconds=time.time()-start,trust=tr),indent=2))
    if q.returncode or not all(tr.values()):raise RuntimeError(f'{tag}: exit={q.returncode}, trust={tr}; inspect saved evidence')
    return json.loads(q.stdout)
