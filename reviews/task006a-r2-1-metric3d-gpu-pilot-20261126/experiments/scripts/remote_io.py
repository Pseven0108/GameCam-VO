"""Pinned SSH transport for the independent R2.1 run. No model imports."""
import argparse,hashlib,json,os,pathlib,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[2]
HOST='sc01-ssh.gpuhome.cc'
PORT='31136'
PIN='SHA256:u1vPsq3oZJFNIp4O3T2wFQLTXqBDLRhR8QmjJ9cw4VA'
KNOWN=pathlib.Path(r'D:\aaa\GameCam-VO\experiments\VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408\evidence\sc01-30723.known_hosts')
KEY=pathlib.Path.home()/'.ssh/id_ed25519_rivermind_codex'
SSH=pathlib.Path(os.environ['WINDIR'])/'System32/OpenSSH/ssh.exe'
REMOTE_ROOT='/root/rivermind-data/GAMECAM_TASK006A_R2_1_GPU_PILOT_20261126_R1'
PY='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'

def ssh_options():
 known_pin=subprocess.check_output([str(SSH.with_name('ssh-keygen.exe')),'-lf',str(KNOWN),'-E','sha256'],text=True,creationflags=subprocess.CREATE_NO_WINDOW)
 if PIN not in known_pin or not KEY.is_file():raise RuntimeError('Missing established host identity/key')
 opt={'BatchMode':'yes','IdentitiesOnly':'yes','StrictHostKeyChecking':'yes','UserKnownHostsFile':str(KNOWN),
 'GlobalKnownHostsFile':'none','HostKeyAlias':'[sc01-ssh.gpuhome.cc]:30723','HostKeyAlgorithms':'ssh-ed25519',
 'UpdateHostKeys':'no','ForwardAgent':'no','ForwardX11':'no','ConnectionAttempts':'1','ConnectTimeout':'10'}
 return ['-F','none','-i',str(KEY)]+[item for k,v in opt.items() for item in ['-o',k+'='+v]]

def run_read(script,label,timeout=65):
 target=ROOT/'00_preflight'
 args=[str(SSH),'-v','-T','-p',PORT,*ssh_options(),HOST.join(['root@','']),
       'exec env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -u -']
 start=time.time()
 with (target/(label+'.stdout.txt')).open('xb') as out,(target/(label+'.stderr.txt')).open('xb') as err:
  p=subprocess.run(args,input=pathlib.Path(script).read_bytes(),stdout=out,stderr=err,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
 log=(target/(label+'.stderr.txt')).read_text(encoding='utf-8',errors='replace')
 r={'endpoint':HOST+':'+PORT,'exit_code':p.returncode,'elapsed_seconds':time.time()-start,
    'host_key_verified':('Server host key: ssh-ed25519 '+PIN in log and 'is known and matches the ED25519 host key' in log),
    'publickey_authenticated':'using "publickey"' in log,'CPU_read_only':True}
 (target/(label+'.receipt.json')).write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(r))
 if p.returncode or not(r['host_key_verified'] and r['publickey_authenticated']):raise RuntimeError('Trusted read failed')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('script');p.add_argument('label');p.add_argument('--timeout',type=int,default=65)
 a=p.parse_args();run_read(a.script,a.label,a.timeout)
