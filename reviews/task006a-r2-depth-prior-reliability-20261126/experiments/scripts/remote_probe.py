"""No-model, read-only GPU/identity probe via the historical user-trusted SSH pin."""
import hashlib,json,os,pathlib,subprocess,time

ROOT=pathlib.Path(__file__).resolve().parents[2]
PIN='SHA256:u1vPsq3oZJFNIp4O3T2wFQLTXqBDLRhR8QmjJ9cw4VA'
KNOWN=pathlib.Path(r'D:\aaa\GameCam-VO\experiments\VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408\evidence\sc01-30723.known_hosts')
KEY=pathlib.Path.home()/'.ssh/id_ed25519_rivermind_codex'
EXE=pathlib.Path(os.environ['WINDIR'])/'System32/OpenSSH/ssh.exe'
REMOTE=r'''
import os,json,subprocess,pathlib,shutil,socket
def run(args):
 try:
  p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=15)
  return {'command':args,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
 except Exception as e: return {'command':args,'error':str(e)}
def listing(path):
 p=pathlib.Path(path)
 return [str(x) for x in sorted(p.iterdir())] if p.is_dir() else []
paths=['/root/rivermind-data','/root/.cache/torch/hub','/opt/gamecam-viper-fullseq-3090-20261120-061408']
out={'hostname':socket.gethostname(),'GPU':run(['nvidia-smi','--query-gpu=name,uuid,memory.total,memory.free','--format=csv,noheader']),
 'GPU_processes':run(['nvidia-smi','--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader']),
 'filesystems':{p:{'total':shutil.disk_usage(p).total,'free':shutil.disk_usage(p).free} for p in ['/root/rivermind-data','/dev/shm'] if pathlib.Path(p).exists()},
 'paths':{p:listing(p) for p in paths},'models_loaded':False,'CUDA_initialized':False}
out['checkpoint_files']=[{'path':str(p),'bytes':p.stat().st_size} for p in pathlib.Path('/root/.cache/torch/hub/checkpoints').glob('*') if p.is_file()]
out['active_python_processes']=run(['ps','-eo','pid,comm'])
py='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'
if pathlib.Path(py).is_file():
 out['package_metadata']=run([py,'-B','-c',"import json,importlib.metadata as m; print(json.dumps({x:m.version(x) for x in ['torch','torchvision','numpy','opencv-python','timm']},indent=2))"])
print(json.dumps(out,indent=2))
'''

def ssh_base():
 pin=subprocess.run([str(EXE.with_name('ssh-keygen.exe')),'-lf',str(KNOWN),'-E','sha256'],capture_output=True,text=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW).stdout
 assert PIN in pin and KEY.is_file()
 args=[str(EXE),'-F','none','-v','-T','-p','30601','-i',str(KEY)]
 opts={'BatchMode':'yes','IdentitiesOnly':'yes','StrictHostKeyChecking':'yes','UserKnownHostsFile':str(KNOWN),
 'GlobalKnownHostsFile':'none','HostKeyAlias':'[sc01-ssh.gpuhome.cc]:30723','HostKeyAlgorithms':'ssh-ed25519',
 'UpdateHostKeys':'no','ForwardAgent':'no','ForwardX11':'no','ClearAllForwardings':'yes','ConnectionAttempts':'1','ConnectTimeout':'10'}
 for k,v in opts.items(): args += ['-o',k+'='+v]
 return args

def main():
 out=ROOT/'00_project_audit'
 args=ssh_base()
 args += ['root@sc01-ssh.gpuhome.cc','exec env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -u -']
 started=time.time()
 with (out/'REMOTE_PROBE.stdout.txt').open('xb') as fo,(out/'REMOTE_PROBE.stderr.txt').open('xb') as fe:
  p=subprocess.run(args,input=REMOTE.encode(),stdout=fo,stderr=fe,timeout=65,creationflags=subprocess.CREATE_NO_WINDOW)
 log=(out/'REMOTE_PROBE.stderr.txt').read_text(encoding='utf-8',errors='replace')
 receipt={'exit_code':p.returncode,'elapsed_seconds':time.time()-started,'endpoint':'sc01-ssh.gpuhome.cc:30601',
 'expected_pin':PIN,'server_host_key_matches_pin':('Server host key: ssh-ed25519 '+PIN in log and 'is known and matches the ED25519 host key' in log),
 'public_key_authenticated':'using "publickey"' in log,'model_loaded':False,'GPU_compute_started':False}
 (out/'REMOTE_PROBE_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(receipt,indent=2))
 if p.returncode==0:
  print((out/'REMOTE_PROBE.stdout.txt').read_text(encoding='utf-8'))
 return p.returncode

if __name__=='__main__': raise SystemExit(main())
