"""Pinned, one-attempt SSH for this authorized native-integration workspace."""
import base64, hashlib, importlib.util, json, os, pathlib, shlex, subprocess
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
BOOT = pathlib.Path(r'D:/aaa/GameCam-VO/experiments/DROID_W_TASK004A_GPU_SCREENING_20261123T082038066Z/bootstrap')
spec = importlib.util.spec_from_file_location('pinned_ssh_only', BOOT/'run_once.py')
ssh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssh)
PRE = json.loads((BOOT/'evidence/preflight.json').read_text())

def run(label, code, timeout=180, python='/usr/bin/python3', cpu=True, input_bytes=None):
    out, err = ROOT/'logs'/(label+'.stdout.txt'), ROOT/'logs'/(label+'.stderr.txt')
    if out.exists() or err.exists():
        raise RuntimeError('Attempt already recorded; no automatic retry: '+label)
    loader = 'import base64;exec(compile(base64.b64decode('+repr(base64.b64encode(code.encode()).decode())+'),"<native-integration>","exec"))'
    command = 'exec env PYTHONDONTWRITEBYTECODE=1 '+('CUDA_VISIBLE_DEVICES= ' if cpu else '')+shlex.quote(python)+' -B -u -c '+shlex.quote(loader)
    started = datetime.now(timezone.utc).isoformat()
    with out.open('xb') as of, err.open('xb') as ef:
        q = subprocess.run(ssh.ssh_base(PRE)+['-o','ClearAllForwardings=yes',ssh.HOST,command], input=input_bytes, stdout=of, stderr=ef, timeout=timeout, creationflags=ssh.CREATE)
    trust=ssh.verified(err)
    receipt={'started':started,'finished':datetime.now(timezone.utc).isoformat(), 'exit_code':q.returncode, 'trust':trust, 'code_sha256':hashlib.sha256(code.encode()).hexdigest(), 'python':python,'cpu_only_environment':cpu}
    (ROOT/'evidence'/(label+'_receipt.json')).write_text(json.dumps(receipt,indent=2))
    if q.returncode or not all(trust.values()):
        raise RuntimeError(receipt)
    return out.read_text(encoding='utf-8')

