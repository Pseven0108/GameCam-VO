"""Pinned, single SSH attempt; read-only dataset metadata, no GPU queries."""
from pathlib import Path
import json, os, subprocess, time

OUT=Path(__file__).resolve().parent
SSH=Path(os.environ['WINDIR'])/'System32/OpenSSH/ssh.exe'
KNOWN=Path('D:/aaa/GameCam-VO/experiments/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/evidence/sc01-30723.known_hosts')
PIN='SHA256:u1vPsq3oZJFNIp4O3T2wFQLTXqBDLRhR8QmjJ9cw4VA'
key=Path.home()/'.ssh/id_ed25519_rivermind_codex'
assert PIN in subprocess.check_output([str(SSH.with_name('ssh-keygen.exe')),'-lf',str(KNOWN),'-E','sha256'],text=True)
options={'BatchMode':'yes','IdentitiesOnly':'yes','StrictHostKeyChecking':'yes','UserKnownHostsFile':str(KNOWN),'GlobalKnownHostsFile':'none','HostKeyAlias':'[sc01-ssh.gpuhome.cc]:30723','HostKeyAlgorithms':'ssh-ed25519','UpdateHostKeys':'no','ForwardAgent':'no','ForwardX11':'no','ConnectionAttempts':'1','ConnectTimeout':'10'}
args=[str(SSH),'-v','-F','none','-T','-i',str(key),'-p','31454']+[x for k,v in options.items() for x in ['-o',k+'='+v]]+['root@sc01-ssh.gpuhome.cc','exec env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -']
script=r'''
import json,os,shutil,stat
from pathlib import Path
from collections import defaultdict
root=Path('/root/rivermind-data'); groups=defaultdict(lambda:{'files':0,'bytes':0,'samples':[]}); matches=[];links=[]
skip={'.git','__pycache__','site-packages','node_modules','envs','external_models','weights','source','sources','repos','conda','miniconda3'}
for here,dirs,files in os.walk(root,followlinks=False):
    current=Path(here); dirs[:]=[n for n in dirs if n.lower() not in skip and not (current/n).is_symlink()]
    for name in files:
        p=current/name
        try:
            if p.is_symlink():continue
            s=p.stat(); parts=p.relative_to(root).parts
        except OSError:continue
        g=groups['/'.join(parts[:min(3,len(parts)-1)])];g['files']+=1;g['bytes']+=s.st_size
        if len(g['samples'])<3:g['samples'].append(str(p))
        low=str(p).lower()
        if any(t in low for t in ('wildworld','omniworld','/owg','vjlz_cbasla','rgb.mp4','skeleton.npz')) and '/reviews/' not in low:
            matches.append({'path':str(p),'bytes':s.st_size,'inode':s.st_ino,'device':s.st_dev,'mtime_ns':s.st_mtime_ns})
result={'root':str(root),'hostname':os.uname().nodename,'volumes':{p:dict(zip(['total','used','free'],shutil.disk_usage(p))) for p in ['/','/root/rivermind-data']},'root_entries':[p.name for p in root.iterdir()],'groups':dict(groups),'name_matches':matches}
print(json.dumps(result,indent=2))
'''
start=time.time()
try:
    r=subprocess.run(args,input=script.encode(),capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
    (OUT/'SSH_READONLY.stderr.log').write_bytes(r.stderr)
    verified=PIN in r.stderr.decode(errors='replace') and 'is known and matches the ED25519 host key' in r.stderr.decode(errors='replace')
    receipt={'endpoint':'sc01-ssh.gpuhome.cc:31454','host_key_verified':verified,'exit_code':r.returncode,'elapsed_seconds':time.time()-start,'gpu_initialized':False}
    (OUT/'REMOTE_CONNECTION.json').write_text(json.dumps(receipt,indent=2))
    if not verified or r.returncode:
        print(json.dumps(receipt));print(r.stderr.decode(errors='replace')[-1000:]);raise SystemExit(1)
    (OUT/'REMOTE_DISCOVERY.json').write_bytes(r.stdout)
    data=json.loads(r.stdout);print('REMOTE VOLUMES',json.dumps(data['volumes']));print('REMOTE TOP DATA',data['root_entries'])
    for name,g in sorted(data['groups'].items(),key=lambda x:x[1]['bytes'],reverse=True)[:35]:print(round(g['bytes']/1024**3,3),g['files'],name,'SAMPLE',g['samples'][0])
    print('MATCHES',len(data['name_matches']))
except subprocess.TimeoutExpired:
    (OUT/'REMOTE_CONNECTION.json').write_text(json.dumps({'status':'CONNECTION_OR_READONLY_SCAN_TIMEOUT','endpoint':'sc01-ssh.gpuhome.cc:31454','elapsed_seconds':time.time()-start}))
    print('Single pinned SSH attempt timed out; no mutation attempted.')
