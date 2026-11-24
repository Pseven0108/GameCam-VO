from transport import *
code=r'''import sys,pathlib,json,os,time,subprocess,socket
s=json.loads(sys.stdin.readline());root=pathlib.Path(s['root']);d=root/'evidence/RERUN_DISK_RECORD_PROBE';d.mkdir();out=d/'synthetic.rrd';bin=s['bin']
argv=[bin,'--bind','127.0.0.1','--port','9875','--serve-web','--web-viewer-port','9876','--ws-server-port','9877','--server-memory-limit','768MB','--save',str(out)]
with (d/'service.stdout.txt').open('wb') as so,(d/'service.stderr.txt').open('wb') as se:
 p=subprocess.Popen(argv,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',RERUN_NO_ANALYTICS='1'),stdout=so,stderr=se)
 try:
  for _ in range(40):
   assert p.poll() is None,'Rerun exited'
   with socket.socket() as conn:
    if conn.connect_ex(('127.0.0.1',9875))==0:break
   time.sleep(.2)
  c="import rerun as r;r.init('task004b_record_probe',recording_id='task004b_record_probe');r.connect_tcp('127.0.0.1:9875');r.log('probe',r.Points3D([[0,0,0],[1,1,1]]));r.disconnect()"
  x=subprocess.run([s['python'],'-B','-c',c],env=dict(os.environ,CUDA_VISIBLE_DEVICES='',RERUN_NO_ANALYTICS='1'),capture_output=True,text=True,timeout=30);assert x.returncode==0,x.stderr
  time.sleep(.5)
 finally:
  p.terminate();p.wait(timeout=15)
 y=subprocess.run([bin,'rrd','print',str(out)],capture_output=True,text=True,timeout=30)
 report=dict(probe='SYNTHETIC_ONLY',service_exit=p.returncode,recording_bytes=out.stat().st_size,print_exit=y.returncode,print_stdout=y.stdout,print_stderr=y.stderr,torch_imported=False,model_runs=0,argv=argv)
 (d/'REPORT.json').write_text(json.dumps(report,indent=2));assert y.returncode==0 and out.stat().st_size>0
 print(json.dumps(report))
'''
d=rpc(code,dict(root=REMOTE,bin=json.loads((A/'bootstrap/evidence/BOOTSTRAP_PASS.json').read_text())['viewer']['native_identity']['executable'],python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'),'NATIVE_RERUN_RECORDING_PROBE',timeout=120);print(json.dumps(d))
