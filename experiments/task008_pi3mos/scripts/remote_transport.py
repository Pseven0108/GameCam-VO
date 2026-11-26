"""Task008 isolated SSH transport pinned to the previously trusted ED25519 key."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT.parents[1]
SSH=Path(os.environ['WINDIR'])/'System32/OpenSSH/ssh.exe'
KEY=Path.home()/'.ssh/id_ed25519_rivermind_codex'
KNOWN=PROJECT/'experiments/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/evidence/sc01-30723.known_hosts'
PIN='SHA256:u1vPsq3oZJFNIp4O3T2wFQLTXqBDLRhR8QmjJ9cw4VA'
ENDPOINT='sc01-ssh.gpuhome.cc'
PORT='31454'


def options():
    info=subprocess.check_output([str(SSH.with_name('ssh-keygen.exe')),'-lf',str(KNOWN),'-E','sha256'],text=True)
    assert PIN in info,'Trusted saved host key mismatch'
    opts={'BatchMode':'yes','IdentitiesOnly':'yes','StrictHostKeyChecking':'yes','UserKnownHostsFile':str(KNOWN),
          'GlobalKnownHostsFile':'none','HostKeyAlias':'[sc01-ssh.gpuhome.cc]:30723','HostKeyAlgorithms':'ssh-ed25519',
          'UpdateHostKeys':'no','ForwardAgent':'no','ForwardX11':'no','ConnectionAttempts':'1','ConnectTimeout':'10'}
    return ['-F','none','-i',str(KEY)]+[v for k,x in opts.items() for v in ['-o',k+'='+x]]


def run(script,label,timeout=180,python='/usr/bin/python3',gpu=False):
    logs=ROOT/'logs';logs.mkdir(exist_ok=True)
    command='exec env PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 '
    if not gpu:command+='CUDA_VISIBLE_DEVICES= '
    command+=shlex.quote(python)+' -B -u -'
    args=[str(SSH),'-v','-T','-p',PORT,*options(),'root@'+ENDPOINT,command]
    start=time.perf_counter()
    with (logs/(label+'.stdout.txt')).open('xb') as out,(logs/(label+'.stderr.txt')).open('xb') as err:
        p=subprocess.run(args,input=script.encode('utf-8'),stdout=out,stderr=err,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
    s=(logs/(label+'.stderr.txt')).read_text('utf-8',errors='replace')
    verified=('Server host key: ssh-ed25519 '+PIN in s and 'is known and matches the ED25519 host key' in s)
    receipt={'endpoint':ENDPOINT+':'+PORT,'host_key_verified':verified,'host_key_pin':PIN,'exit_code':p.returncode,
             'elapsed_seconds':time.perf_counter()-start,'GPU_visibility_enabled':gpu,'script_sha256':hashlib.sha256(script.encode()).hexdigest()}
    with (logs/(label+'.receipt.json')).open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2);f.write('\n')
    if not verified or p.returncode:raise RuntimeError('Remote command failed; inspect the saved task logs without exposing credentials')
    return (logs/(label+'.stdout.txt')).read_text('utf-8')


if __name__=='__main__':
    script=Path(sys.argv[1]);label=sys.argv[2]
    print(run(script.read_text('utf-8'),label,timeout=int(sys.argv[3]) if len(sys.argv)>3 else 180))
