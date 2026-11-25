import pathlib,json,base64
from local_remote import run,ROOT
assert json.loads((ROOT/'03_tests/CPU_TEST_REPORT.json').read_text())['PASS']
files={'tools/replay_r3.py':base64.b64encode((ROOT/'01_runtime/replay_r3.py').read_bytes()).decode()}
launcher='''import pathlib,subprocess,json,os,time,traceback
r=pathlib.Path(__file__).resolve().parents[1];e=r/'evidence/run';start=time.time()
with (e/'stdout.txt').open('xb') as fo,(e/'stderr.txt').open('xb') as fe:
 p=subprocess.run([os.sys.executable,'-B','-u',str(r/'tools/replay_r3.py')],stdin=subprocess.DEVNULL,stdout=fo,stderr=fe)
(e/'PROCESS_RECEIPT.json').write_text(json.dumps({'exit_code':p.returncode,'started_unix':start,'finished_unix':time.time(),'automatic_retry':False},indent=2)+'\\n')
'''
files['tools/launch_run.py']=base64.b64encode(launcher.encode()).decode()
script='''import pathlib,json,base64,subprocess,os,shutil,time,hashlib
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_R3_REDUCTION_U_ISOLATION_20261125_R1')
assert json.loads((r/'build/BUILD_COMPLETE.json').read_text())['PASS']
assert not (r/'results').exists() and not (r/'evidence/run').exists()
assert shutil.disk_usage(r).free>10*1024**3+1280*1024**2
probe=subprocess.run(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],capture_output=True,text=True,timeout=15)
assert probe.returncode==0 and not probe.stdout.strip(), 'Other GPU process present'
files=PAYLOAD
for n,b in files.items():
 p=r/n;p.parent.mkdir(exist_ok=True,parents=True)
 with p.open('xb') as f:f.write(base64.b64decode(b))
e=r/'evidence/run';e.mkdir()
with (e/'launcher.log').open('xb') as fo:
 p=subprocess.Popen([os.sys.executable,'-B','-u',str(r/'tools/launch_run.py')],stdin=subprocess.DEVNULL,stdout=fo,stderr=subprocess.STDOUT,start_new_session=True)
(e/'STARTED.json').write_text(json.dumps({'pid':p.pid,'started_unix':time.time(),'launches':1,'gpu_BA_call_budget':20,'isolated_calls_each':16,'automatic_retry':False},indent=2))
print(json.dumps({'started_pid':p.pid,'tools_SHA':{n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in files}},indent=2),flush=True)
'''.replace('PAYLOAD',repr(files))
(ROOT/'00_intake/DEPLOY_RUN.script.py').write_text(script)
print(run(script.encode(),'DEPLOY_RUN',python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python',gpu=True,timeout=45))
