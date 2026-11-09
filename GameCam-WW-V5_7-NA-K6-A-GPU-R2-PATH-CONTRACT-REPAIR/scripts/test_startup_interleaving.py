"""Run the real Supervisor interleaving probe in an isolated CPU subprocess."""
import os,pathlib,subprocess,sys,json

def test_cuda_sample_refreshes_older_status(tmp_path):
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1');env.pop('PYTHONPYCACHEPREFIX',None)
 script=pathlib.Path(__file__).with_name('startup_status_cuda_race_probe.py')
 r=subprocess.run([sys.executable,'-B',str(script),str(tmp_path)],env=env,capture_output=True,text=True,timeout=20)
 assert r.returncode==0,r.stdout+r.stderr
 x=json.loads((tmp_path/'STATUS_CUDA_INTERLEAVING_TEST.json').read_text());assert x['passed'];assert x['interleaving']
 assert x['result']['worker_fully_exited'] and x['result']['monitor_fully_exited'] and x['result']['ipc_cleanup']['passed']
