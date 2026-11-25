import pathlib,json,base64,subprocess,os,shutil,hashlib
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_R2_NUMERICAL_EQUIVALENCE_20261125_R1')
phase='trace'
assert json.loads((r/'evidence/plain/PROCESS_RECEIPT.json').read_text())['exit_code']==0
assert shutil.disk_usage(r).free>11*1024**3
files={}
for n,b in files.items():
 p=r/n;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as f:f.write(base64.b64decode(b))
if phase=='trace':assert json.loads((r/'build/BUILD_COMPLETE.json').read_text())['PASS']
log=r/(phase+'_wrapper.log');env=os.environ.copy()
if phase=='build':env['CUDA_VISIBLE_DEVICES']=''
with log.open('xb') as fo:
 p=subprocess.Popen([os.sys.executable,'-B','-u',str(r/'tools/launch_phase.py'),phase],stdin=subprocess.DEVNULL,stdout=fo,stderr=subprocess.STDOUT,start_new_session=True,env=env)
(r/(phase.upper()+'_PID.json')).write_text(json.dumps({'pid':p.pid,'launches':1}))
print(json.dumps({'started_pid':p.pid,'phase':phase,'uploaded':{n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in files}}),flush=True)
