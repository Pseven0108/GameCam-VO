"""Transfer only this task's code/config to a new remote directory."""
import hashlib,io,json,os,shlex,subprocess,tarfile
from pathlib import Path
from common import TASK,dump
from remote_transport import SSH,options

REMOTE='/root/rivermind-data/GAMECAM_TASK011B_20261127_R1'


def transfer(initial=False):
    candidates=[]
    for folder in ('scripts','configs','CADP_DR_CONFIGS','CADP_DR_EXPERIMENTAL_BRANCH','gpu'):
        base=TASK/folder
        if base.exists():candidates += [p for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    mem=io.BytesIO()
    with tarfile.open(fileobj=mem,mode='w:gz') as t:
        for p in candidates:t.add(p,arcname=str(p.relative_to(TASK)).replace('\\','/'),recursive=False)
    content=mem.getvalue();identity=hashlib.sha256(content).hexdigest()
    # The target is a new task directory; never traverse or overwrite a baseline.
    script=f'''import sys,tarfile,io,hashlib,json\nfrom pathlib import Path\np=Path({REMOTE!r})\nif {initial!r} and p.exists():raise RuntimeError("Preserve existing task directory")\np.mkdir(parents=True,exist_ok=True)\nb=sys.stdin.buffer.read()\nassert hashlib.sha256(b).hexdigest()=={identity!r}\nwith tarfile.open(fileobj=io.BytesIO(b),mode="r:gz") as t:\n for m in t.getmembers():\n  dst=(p/m.name).resolve()\n  assert dst.is_relative_to(p.resolve()) and m.isfile() and not m.issym()\n  dst.parent.mkdir(parents=True,exist_ok=True)\n  dst.write_bytes(t.extractfile(m).read())\nprint(json.dumps(dict(target=str(p),files={len(candidates)},sha256={identity!r})))'''
    command='/usr/bin/python3 -c '+shlex.quote(script)
    r=subprocess.run([str(SSH),'-T','-p','31454',*options(),'root@sc01-ssh.gpuhome.cc',command],input=content,capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace'))
    dump(TASK/'private/GPU_TRANSFER_LATEST.json',dict(target=REMOTE,files=len(candidates),sha256=identity,stdout=r.stdout.decode(),exit_code=r.returncode))
    print(r.stdout.decode())


if __name__=='__main__':
    import sys
    transfer('--initial' in sys.argv)
