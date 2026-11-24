import sys, pathlib, json, subprocess, shlex, base64
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bootstrap'))
from run_once import ssh_base, HOST, CREATE, verified
PRE=json.loads((ROOT/'bootstrap/evidence/preflight.json').read_text())
def rpc(code, name, timeout=240, payload=None):
    loader="import sys,base64;exec(compile(base64.b64decode(sys.stdin.readline()),'<authorized-cpu-control>','exec'))"
    cmd='exec env CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /usr/bin/python3 -I -B -u -c '+shlex.quote(loader)
    data=base64.b64encode(code.encode())+b'\n'
    if payload is not None:data+=json.dumps(payload).encode()+b'\n'
    p=subprocess.run(ssh_base(PRE)+['-o','ClearAllForwardings=yes',HOST,cmd],input=data,capture_output=True,timeout=timeout,creationflags=CREATE)
    (ROOT/'evidence'/f'{name}.stdout.txt').write_bytes(p.stdout)
    err=ROOT/'evidence'/f'{name}.ssh.stderr.txt';err.write_bytes(p.stderr)
    assert all(verified(err).values()),'SSH trust/public-key identity failed'
    print(p.stdout.decode(errors='replace')[-5000:],flush=True)
    if p.returncode:raise RuntimeError(f'{name} exit {p.returncode}: '+p.stderr.decode(errors='replace')[-1500:])
    return p.stdout
