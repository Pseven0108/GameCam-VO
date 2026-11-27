"""Pinned, task-local transport; no host-key acceptance or system config edits."""
import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path

from common import TASK,dump

PIN='SHA256:u1vPsq3oZJFNIp4O3T2wFQLTXqBDLRhR8QmjJ9cw4VA'
KNOWN=Path('D:/aaa/GameCam-VO/experiments/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/evidence/sc01-30723.known_hosts')
KEY=Path.home()/'.ssh/id_ed25519_rivermind_codex'
SSH=Path(os.environ['WINDIR'])/'System32/OpenSSH/ssh.exe'


def options():
    fingerprint=subprocess.check_output([str(SSH.with_name('ssh-keygen.exe')),'-lf',str(KNOWN),'-E','sha256'],text=True)
    if PIN not in fingerprint:raise RuntimeError('Saved trusted host identity changed')
    settings={'BatchMode':'yes','IdentitiesOnly':'yes','StrictHostKeyChecking':'yes','UserKnownHostsFile':str(KNOWN),
        'GlobalKnownHostsFile':'none','HostKeyAlias':'[sc01-ssh.gpuhome.cc]:30723','HostKeyAlgorithms':'ssh-ed25519',
        'UpdateHostKeys':'no','ForwardAgent':'no','ForwardX11':'no','ConnectionAttempts':'1','ConnectTimeout':'10',
        'ServerAliveInterval':'30','ServerAliveCountMax':'3'}
    return ['-F','none','-i',str(KEY)]+[item for k,v in settings.items() for item in ('-o',k+'='+v)]


def run(script,label,port='31454',python='/usr/bin/python3',timeout=60):
    logs=TASK/'private/remote';logs.mkdir(parents=True,exist_ok=True)
    if (logs/(label+'.json')).exists():raise FileExistsError('Preserve every remote receipt')
    command='exec env PYTHONDONTWRITEBYTECODE=1 '+shlex.quote(python)+' -B -'
    args=[str(SSH),'-v','-T','-p',str(port),*options(),'root@sc01-ssh.gpuhome.cc',command]
    p=subprocess.run(args,input=script.encode('utf-8'),capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
    stderr=p.stderr.decode('utf-8',errors='replace')
    verified=('Server host key: ssh-ed25519 '+PIN in stderr and 'is known and matches the ED25519 host key' in stderr)
    (logs/(label+'.stdout')).write_bytes(p.stdout);(logs/(label+'.stderr')).write_bytes(p.stderr)
    dump(logs/(label+'.json'),dict(port=str(port),host_key_pin=PIN,host_key_verified=verified,exit_code=p.returncode,
        command_script_sha256=hashlib.sha256(script.encode()).hexdigest(),model_run_started=False))
    if not verified or p.returncode:raise RuntimeError('Remote read-only command failed; see private task receipt')
    return p.stdout.decode('utf-8')
