"""Transfer a fresh official clone only after recorded remote checkout timeout."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

from remote_transport import ROOT,SSH,PORT,ENDPOINT,options

SOURCE=Path(r'D:\aaa\external_models\Pi3MOS-SLAM_TASK008_FRESH.bundle')
b=SOURCE.read_bytes();assert len(b)<128*1024**2
h=hashlib.sha256(b).hexdigest()
script='''import hashlib,json,pathlib,subprocess,sys
work=pathlib.Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1')
bundle=work/'official_source_fresh_clone.bundle'
repo=pathlib.Path('/root/rivermind-data/external_models/Pi3MOS-SLAM_1b81d729c4259a5a775eb4aae41f959eea38ae14_LOCAL_CLONE')
assert not bundle.exists() and not repo.exists()
data=sys.stdin.buffer.read({size}+1)
assert len(data)=={size} and hashlib.sha256(data).hexdigest()=={digest}
with bundle.open('xb') as f:f.write(data)
with (work/'logs/LOCAL_FRESH_CLONE_TRANSFER.log').open('xb') as log:
 subprocess.run(['git','clone',str(bundle),str(repo)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
 subprocess.run(['git','-C',str(repo),'checkout','--detach','1b81d729c4259a5a775eb4aae41f959eea38ae14'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
status=subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True)
assert head=='1b81d729c4259a5a775eb4aae41f959eea38ae14' and not status
receipt=dict(source_method='Fresh official clone on local PC after actual remote checkout timeout',source_HEAD=head,source_worktree=status,bundle_bytes=len(data),bundle_sha256=hashlib.sha256(data).hexdigest(),source_directory=str(repo),old_failed_clone_preserved=True)
(work/'SOURCE_ACQUISITION_VERIFIED.json').write_text(json.dumps(receipt,indent=2)+'\\n')
print(json.dumps(receipt,indent=2))
'''.format(size=len(b),digest=repr(h))
cmd='exec env GIT_TERMINAL_PROMPT=0 GIT_LFS_SKIP_SMUDGE=1 /usr/bin/python3 -u -c '+shlex.quote(script)
args=[str(SSH),'-T','-p',PORT,*options(),'root@'+ENDPOINT,cmd]
r=subprocess.run(args,input=b,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW)
assert r.returncode==0,'Source transfer failed; preserve local source and remote log'
data=json.loads(r.stdout)
p=ROOT/'logs/SOURCE_ACQUISITION_VERIFIED.json'
with p.open('x',encoding='utf-8') as f:json.dump(data,f,indent=2);f.write('\n')
print(json.dumps(data,indent=2))
