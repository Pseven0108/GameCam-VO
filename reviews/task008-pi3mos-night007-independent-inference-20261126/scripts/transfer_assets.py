"""Streaming transfer of exact official wheels/checkpoint; no model execution."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

from remote_transport import ROOT,SSH,PORT,ENDPOINT,options


def transfer(local,remote_dir,expected=None):
    local=Path(local);size=local.stat().st_size
    assert size<5*1024**3 and local.name==Path(local.name).name
    h=hashlib.sha256()
    with local.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    digest=h.hexdigest()
    if expected:assert expected['bytes']==size and expected['sha256']==digest
    script='''import hashlib,json,pathlib,sys
p=pathlib.Path({dest});p.parent.mkdir(parents=True,exist_ok=True)
assert not p.exists()
h=hashlib.sha256();count=0
with p.open('xb') as f:
 while True:
  b=sys.stdin.buffer.read(8*1024**2)
  if not b:break
  count+=len(b)
  if count>{size}:raise RuntimeError('Transfer size limit')
  h.update(b);f.write(b)
assert count=={size} and h.hexdigest()=={sha}
print(json.dumps({{'path':str(p),'bytes':count,'sha256':h.hexdigest(),'verified':True}}))
'''.format(dest=repr(remote_dir+'/'+local.name),size=size,sha=repr(digest))
    cmd='exec /usr/bin/python3 -u -c '+shlex.quote(script)
    with local.open('rb') as f:
        r=subprocess.run([str(SSH),'-T','-p',PORT,*options(),'root@'+ENDPOINT,cmd],stdin=f,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                         timeout=3600,creationflags=subprocess.CREATE_NO_WINDOW)
    assert r.returncode==0,'Asset transfer failed; retain source and partial remote file'
    return json.loads(r.stdout)


def main():
    mode=sys.argv[1];rows=[]
    if mode=='wheels':
        for p in sorted(Path(r'D:\aaa\external_models\task008-linux-wheels').glob('*.whl')):
            rows.append(transfer(p,'/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1/wheelhouse'))
    elif mode=='dependency_wheels':
        for p in sorted(Path(r'D:\aaa\external_models\task008-linux-dependency-wheels').glob('*.whl')):
            rows.append(transfer(p,'/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1/wheelhouse'))
    elif mode=='weight':
        r=json.loads(Path(r'D:\aaa\external_models\pi3mos_task008_weights\DOWNLOAD_STATE.json').read_text('utf-8'));assert r['stage']=='COMPLETE'
        rows.append(transfer(r['local_path'],'/root/rivermind-data/external_models/pi3mos_task008_weights',r))
    else:raise ValueError(mode)
    out=ROOT/'logs'/('ASSET_TRANSFER_'+mode+'.json')
    with out.open('x',encoding='utf-8') as f:json.dump({'assets':rows,'all_SHA256_verified':True,'source':'Exact official download, no model loads'},f,indent=2);f.write('\n')
    print(json.dumps(rows,indent=2))


if __name__=='__main__':main()
