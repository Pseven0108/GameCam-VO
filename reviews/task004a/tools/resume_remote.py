import json, pathlib, subprocess, os, sys, time, socket, signal, hashlib
from datetime import datetime, timezone
spec=json.loads(sys.stdin.readline());root=pathlib.Path(spec['root']);ev=root/'evidence'
utc=lambda:datetime.now(timezone.utc).isoformat()
def put(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2,allow_nan=False)
def listeners():
 rows=[]
 for tab in ['tcp','tcp6']:
  for line in pathlib.Path('/proc/net',tab).read_text().splitlines()[1:]:
   v=line.split();addr,port=v[1].split(':')
   if v[3]=='0A' and int(port,16) in (9875,9876,9877):rows.append(dict(table=tab,address=addr,port=int(port,16),inode=v[9]))
 return rows
assert socket.gethostname()=='jupyter-yd6gks8uzfbxzdb4'
assert not listeners(),'unexpected Rerun port owner'
for arm in ('E3','E4','E7'):
 done=json.loads((root/'results'/arm/'COMPLETE.json').read_text());assert done['status']=='COMPLETE' and done['poses']==487
for arm in spec['remaining']:assert not (root/'results'/arm).exists()
put(ev/'RESUME_AUTHORIZATION_DATA_PRIORITY.json',spec['authorization'])
service_dir=ev/'rerun_data_priority';service_dir.mkdir()
argv=spec['viewer_argv'];assert argv[1:]==['--bind','127.0.0.1','--port','9875','--serve-web','--web-viewer-port','9876','--ws-server-port','9877','--server-memory-limit','768MB']
service=None;finished=[];error=None
try:
 with (service_dir/'stdout.txt').open('xb') as so,(service_dir/'stderr.txt').open('xb') as se:
  service=subprocess.Popen(argv,cwd=service_dir,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',RERUN_NO_ANALYTICS='1'),stdout=so,stderr=se,start_new_session=True)
  pp=pathlib.Path('/proc')/str(service.pid)
  ready=None
  for _ in range(100):
   assert service.poll() is None,'Rerun native process exited'
   rows=listeners()
   if len(rows)==3:
    fds=[]
    for f in (pp/'fd').iterdir():
     try:fds.append(os.readlink(f))
     except FileNotFoundError:pass
    assert all(r['table']=='tcp' and r['address']=='0100007F' and 'socket:['+r['inode']+']' in fds for r in rows)
    assert os.readlink(pp/'exe')==argv[0] and os.readlink(pp/'cwd')==str(service_dir)
    actual=[a.decode() for a in (pp/'cmdline').read_bytes().split(b'\0') if a]
    assert actual==argv
    ready=dict(event='viewer_ready',utc=utc(),pid=service.pid,native_identity=dict(pid=service.pid,ppid=os.getpid(),executable=argv[0],cwd=str(service_dir),argv=argv),listeners=rows,browser_required=False,reason='LATEST_USER_PRIORITIZES_ABLATION_RESULTS')
    break
   time.sleep(.15)
  assert ready is not None,'native loopback service timeout'
  put(service_dir/'SERVICE_RECEIPT.json',ready)
  print(json.dumps(dict(event='DATA_PRIORITY_RESUME',remaining=spec['remaining'],completed_preserved=['E3','E4','E7'],browser_gate_waived=True)),flush=True)
  for arm in spec['remaining']:
   assert service.poll() is None
   args=[sys.executable,'-I','-B','-u','-c',spec['launcher_source']]
   payload=dict(root=str(root),arm=arm,viewer=ready)
   with (ev/('RESUME_'+arm+'.stdout.txt')).open('xb') as out,(ev/('RESUME_'+arm+'.stderr.txt')).open('xb') as err:
    child=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''))
    child.stdin.write(json.dumps(payload).encode()+b'\n');child.stdin.close()
    for line in child.stdout:
     out.write(line);out.flush();sys.stdout.buffer.write(line);sys.stdout.buffer.flush()
    rc=child.wait()
   put(ev/('RESUME_'+arm+'_CONTROL_RECEIPT.json'),dict(arm=arm,exit_code=rc,utc=utc(),no_retry=True))
   assert rc==0,'arm failed: '+arm
   assert (root/'results'/arm/'COMPLETE.json').is_file()
   finished.append(arm)
  put(ev/'ALL_EIGHT_RUNS_COMPLETE.json',dict(utc=utc(),arms=['E3','E4','E7']+finished,model_runs=8,browser_gate_waived_for_remaining=True))
except BaseException as exc:
 error=repr(exc)
 put(ev/'DATA_PRIORITY_RESUME_FAILURE.json',dict(utc=utc(),error=error,finished=finished,no_retry=True))
 raise
finally:
 if service is not None and service.poll() is None:
  service.terminate()
  try:service.wait(timeout=12)
  except subprocess.TimeoutExpired:
   service.kill();service.wait(timeout=5)
 time.sleep(.3)
 after=listeners()
 put(ev/'DATA_PRIORITY_SERVICE_CLEANUP.json',dict(utc=utc(),service_pid=None if service is None else service.pid,service_exit_code=None if service is None else service.poll(),ports_after=after,owned_service_closed=not after,finished=finished,error=error,server_shutdown_performed=False))
 print(json.dumps(dict(event='RESUME_FINISHED',completed=finished,error=error,ports_after=after)),flush=True)