"""Pinned SSH deployment and observation for the explicitly approved R3 retry."""
import hashlib
import io
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tarfile

BASE=Path(__file__).resolve().parent
TASK=BASE/'repo/experiments/TASK011E'
REMOTE='/root/rivermind-data/GAMECAM_TASK011E_FAST_20261128_R3'
PYTHON='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'


def command(code):
    sys.path.insert(0,'D:/aaa/GameCam-VO-TASK011D/experiments/TASK011D')
    api=runpy.run_path('D:/aaa/GameCam-VO-TASK011D/experiments/TASK011D/publish_review.py')
    return api['command'](code)


def remote(code, data=None, timeout=90):
    result=subprocess.run(command(code),input=data,capture_output=True,timeout=timeout,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8','replace')[-6000:])
    return result.stdout


def deploy():
    target=TASK/'test_startup_and_supervision.py'
    if target.exists():raise FileExistsError('Preserve test copy')
    target.write_bytes((BASE/'test_startup_and_supervision.py').read_bytes())
    data=io.BytesIO();records=[]
    with tarfile.open(fileobj=data,mode='w:gz') as archive:
        for path in sorted(TASK.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts:continue
            rel=path.relative_to(TASK).as_posix();raw=path.read_bytes()
            records.append(dict(path=rel,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
            archive.add(path,arcname=rel,recursive=False)
    raw=data.getvalue()
    expected=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),files=records)
    code=r'''
from pathlib import Path,PurePosixPath
import hashlib,io,json,os,shutil,subprocess,sys,tarfile,time
expected=EXPECTED
root=Path(REMOTE);old=root.with_name('GAMECAM_TASK011E_FAST_20261128_R2')
source=old/'repo/experiments/TASK011E'
assert (source/'BATCH_STOPPED.json').is_file(),'Sealed failed attempt must remain available'
assert not root.exists(),'New independent attempt only; never overwrite'
assert not subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
assert shutil.disk_usage(source).free>=10*1024**3
raw=sys.stdin.buffer.read();assert len(raw)==expected['bytes'] and hashlib.sha256(raw).hexdigest()==expected['sha256']
root.mkdir();task=root/'repo/experiments/TASK011E';task.mkdir(parents=True)
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
    members=archive.getmembers();assert len(members)==len(expected['files'])
    for member in members:
        p=PurePosixPath(member.name)
        assert member.isfile() and not p.is_absolute() and '..' not in p.parts
        out=task/member.name;out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('xb') as writer:writer.write(archive.extractfile(member).read())
for record in expected['files']:
    p=task/record['path'];assert p.stat().st_size==record['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==record['sha256']
for name in ('private','cache'):
    (task/name).symlink_to(source/name,target_is_directory=True)
for name in ('TASK011B','TASK011C'):
    (task.parent/name).symlink_to(source.parent/name,target_is_directory=True)
receipt=dict(status='DEPLOYED_NOT_LAUNCHED',root=str(root),files=len(expected['files']),
    old_attempt_preserved=True,cache_copied_or_regenerated=False,
    when_unix=time.time(),package_sha256=expected['sha256'])
(root/'DEPLOYMENT_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
'''.replace('EXPECTED',repr(expected)).replace('REMOTE',repr(REMOTE))
    output=remote(code,raw)
    (BASE/'DEPLOYMENT_RECEIPT.json').write_bytes(output)
    (BASE/'DEPLOYMENT_MANIFEST.json').write_text(json.dumps(expected,indent=2)+'\n',encoding='utf-8')
    print(output.decode())


def preflight():
    code=r'''
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
root=Path(REMOTE);task=root/'repo/experiments/TASK011E';py=PYTHON
assert not (root/'SERVICE_START.json').exists()
p=subprocess.run([py,'-B',str(task/'test_startup_and_supervision.py')],capture_output=True,timeout=90,cwd=task)
(root/'CPU_REGRESSION_STDOUT.txt').write_bytes(p.stdout)
(root/'CPU_REGRESSION_STDERR.txt').write_bytes(p.stderr)
if p.returncode:raise RuntimeError(p.stderr.decode()[-6000:])
check="""import sys,json;from pathlib import Path;sys.path.insert(0,TASK)
from authorization import require_approved_runtime
require_approved_runtime(Path(TASK)/'RUNTIME_AUTHORIZATION.json','END_TO_END','s43_val_038_00448-00511_A4')
from native_binding import verify_upstream_source,verify_candidate_identity
source=verify_upstream_source();extension=verify_candidate_identity()
import torch
assert torch.__version__=='2.1.0+cu118' and torch.version.cuda=='11.8'
assert torch.cuda.is_available() and '3090' in torch.cuda.get_device_name(0)
print(json.dumps(dict(torch=torch.__version__,cuda=torch.version.cuda,device=torch.cuda.get_device_name(0),source=str(source),candidate=str(extension))))
""".replace('TASK',repr(str(task)))
p2=subprocess.run([py,'-B','-c',check],capture_output=True,timeout=150,cwd=task)
(root/'AUTHORIZATION_NATIVE_PREFLIGHT_STDOUT.txt').write_bytes(p2.stdout)
(root/'AUTHORIZATION_NATIVE_PREFLIGHT_STDERR.txt').write_bytes(p2.stderr)
if p2.returncode:raise RuntimeError(p2.stderr.decode()[-6000:])
state=dict(status='PASS',cpu_tests=11,cpu_tests_skipped=0,
    native=json.loads(p2.stdout),disk_free_bytes=shutil.disk_usage(task).free,
    shm_total_bytes=shutil.disk_usage('/dev/shm').total,
    gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.free','--format=csv,noheader'],text=True).strip(),
    model_or_SLAM_run=False,when_unix=time.time())
assert state['disk_free_bytes']>=10*1024**3
(root/'PREFLIGHT_RECEIPT.json').write_text(json.dumps(state,indent=2)+'\n')
print(json.dumps(state))
'''.replace('REMOTE',repr(REMOTE)).replace('PYTHON',repr(PYTHON))
    output=remote(code,timeout=240)
    (BASE/'PREFLIGHT_RECEIPT.json').write_bytes(output)
    print(output.decode())


def launch():
    code=r'''
from pathlib import Path
import json,os,subprocess,time
root=Path(REMOTE);task=root/'repo/experiments/TASK011E'
assert json.loads((root/'PREFLIGHT_RECEIPT.json').read_text())['status']=='PASS'
assert not (root/'SERVICE_START.json').exists(),'No retry or duplicate daemon'
assert not subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
with (root/'SERVICE.log').open('xb') as log:
    process=subprocess.Popen([__RUNTIME_PYTHON__,'-B','-u',str(task/'batch_service.py'),'--approval',str(task/'RUNTIME_AUTHORIZATION.json')],
        stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=env,cwd=task,start_new_session=True)
value=dict(status='STARTED_ONCE',pid=process.pid,root=str(root),when_unix=time.time(),
    explicit_retry_approved=True,automatic_retries=0,prior_attempts_preserved=True)
(root/'SERVICE_START.json').write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps(value))
'''.replace('REMOTE',repr(REMOTE)).replace('__RUNTIME_PYTHON__',repr(PYTHON))
    output=remote(code)
    (BASE/'REMOTE_SERVICE_START.json').write_bytes(output)
    print(output.decode())


if __name__=='__main__':
    {'deploy':deploy,'preflight':preflight,'launch':launch}[sys.argv[1]]()
