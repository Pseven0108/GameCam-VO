import pathlib,json,base64,sys,tarfile,hashlib
from local_remote import run
ROOT=pathlib.Path(__file__).resolve().parents[1]
RECEIVER=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-GPU-20261125-R1')
proof=json.loads((RECEIVER/'snapshot_D0_S1_RGB233.VERIFIED.json').read_text())
pre=json.loads((ROOT/'00_intake/PREFLIGHT.stdout.txt').read_text())
assert pre['gpu']['exit_code']==0 and 'RTX 3090' in pre['gpu']['stdout'] and not pre['gpu_processes']['stdout'].strip()
assert pre['disk']['free']>int(11.5*1024**3) and not pre['new_root_exists']
prefix=proof['remote_source']+'/'
assert all(pre['files'][prefix+n]==v for n,v in proof['members'].items())
files={'tools/replay_r2.py':(ROOT/'01_runtime/replay_r2.py').read_bytes(),'tools/launch_phase.py':(ROOT/'01_runtime/launch_phase.py').read_bytes(),'PROTOCOL.md':(ROOT/'PROTOCOL.md').read_bytes()}
payload={n:base64.b64encode(b).decode() for n,b in files.items()}
script='''import pathlib,base64,json,hashlib,shutil,subprocess,os,importlib.util
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_R2_NUMERICAL_EQUIVALENCE_20261125_R1')
assert not r.exists() and shutil.disk_usage(r.parent).free>int(11.5*1024**3)
native=pathlib.Path(importlib.util.find_spec('droid_backends').origin)
assert hashlib.sha256(native.read_bytes()).hexdigest()=='6dcf8de36cadc2174023b649b026f04e61b1231420d98763cc5aa3b294a91c3e'
r.mkdir()
files=PAYLOAD
for n,b in files.items():
 p=r/n;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as f:f.write(base64.b64decode(b))
print(json.dumps({'installed_original':str(native),'installed_original_sha256':hashlib.sha256(native.read_bytes()).hexdigest(),'uploaded':{n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in files}}),flush=True)
log=r/'plain_wrapper.log'
with log.open('xb') as fo:
 p=subprocess.Popen([os.sys.executable,'-B','-u',str(r/'tools/launch_phase.py'),'plain'],stdin=subprocess.DEVNULL,stdout=fo,stderr=subprocess.STDOUT,start_new_session=True)
(r/'PLAIN_PID.json').write_text(json.dumps({'pid':p.pid,'launches':1}))
print(json.dumps({'started_pid':p.pid,'phase':'plain','max_calls':6}),flush=True)
'''.replace('PAYLOAD',repr(payload))
(ROOT/'00_intake/DEPLOY_PLAIN.script.py').write_text(script)
print(run(script.encode(),'DEPLOY_PLAIN',python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python',gpu=True,timeout=45))
