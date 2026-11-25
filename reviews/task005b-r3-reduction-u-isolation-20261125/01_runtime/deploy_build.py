import pathlib,json,base64,sys
from local_remote import run,ROOT
files={'PROTOCOL.md':base64.b64encode((ROOT/'PROTOCOL.md').read_bytes()).decode()}
for p in (ROOT/'02_candidate').iterdir():
    if p.is_file():files['candidate/'+p.name]=base64.b64encode(p.read_bytes()).decode()
script='''import pathlib,json,base64,subprocess,os,shutil,hashlib,time
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_R3_REDUCTION_U_ISOLATION_20261125_R1')
assert not r.exists()
assert shutil.disk_usage(r.parent).free>10*1024**3+1280*1024**2
r.mkdir()
files=PAYLOAD
for n,b in files.items():
 p=r/n;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as f:f.write(base64.b64decode(b))
e=r/'evidence/build';e.mkdir(parents=True)
env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']=''
with (e/'stdout.txt').open('xb') as fo,(e/'stderr.txt').open('xb') as fe:
 p=subprocess.Popen([os.sys.executable,'-B','-u',str(r/'candidate/build_r3.py')],stdin=subprocess.DEVNULL,stdout=fo,stderr=fe,env=env,start_new_session=True)
(e/'STARTED.json').write_text(json.dumps({'pid':p.pid,'started_unix':time.time(),'automatic_retry':False}))
print(json.dumps({'build_pid':p.pid,'uploaded':{n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in files}},indent=2),flush=True)
'''.replace('PAYLOAD',repr(files))
(ROOT/'00_intake/DEPLOY_BUILD.script.py').write_text(script)
print(run(script.encode(),'DEPLOY_BUILD',python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python',timeout=50))
