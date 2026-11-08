"""Actual WSL CPU consumer: append-only host samples and explicit terminal state."""
import argparse,json,os,sys,time,traceback
from pathlib import Path
from evidence_io import write_new,read_json
from monitor_transport import MonitorReader,MonitorError,await_startup

def consume(root,session,purpose):
 root=Path(root);started=time.time();reads=0;seqs=set();errors=[];expected_events=[];first=None;last=None;terminal=None;passed=False;read_log=None
 try:
  identity=dict(pid=os.getpid(),parent_pid=os.getppid(),monitor_session_id=session,root=str(root),script=str(Path(__file__).resolve()),started_unix=started,proc_start_ticks=Path('/proc/self/stat').read_text().rpartition(')')[2].split()[19])
  write_new(root/'consumer_identity.json',identity)
  read_log=(root/'consumer_reads.jsonl').open('x',encoding='utf-8')
  reader=MonitorReader(root/'logs/windows_monitor.jsonl',session)
  barrier=await_startup(reader,timeout=15);write_new(root/'consumer_startup_barrier.json',dict(passed=True,records=barrier,unix_time=time.time()))
  while True:
   terminal=reader.terminal(allow_completed=True)
   x=reader.read_last(allow_completed=True);seen=time.time();reads+=1;seqs.add(x['sample_seq']);first=first or x;last=x
   read_log.write(json.dumps(dict(read_seq=reads,read_unix=seen,source_unix=x['unix_time'],sample_seq=x['sample_seq'],age_seconds=seen-x['unix_time'],monitor_session_id=session),allow_nan=False)+'\n');read_log.flush()
   if terminal:break
   if time.time()-started>50:raise MonitorError('CONSUMER_CPU_DEADLINE_EXCEEDED')
   time.sleep(.005)
  if purpose!='concurrency':raise MonitorError('EXPECTED_NEGATIVE_EVENT_DID_NOT_OCCUR')
  if terminal['exit_status']!='COMPLETED' or len(seqs)<30 or reads<100:raise MonitorError('CONCURRENCY_MINIMUM_NOT_REACHED')
  passed=True
 except BaseException as e:
  code='PRODUCER_EXIT_FAILED_INITIALIZATION' if purpose=='expect-init-failure' else 'PRODUCER_EXIT_STOPPED' if purpose=='expect-stop' else None
  if code and code in str(e):
   terminal=read_json(root/'logs/windows_monitor.exit.json');elapsed=time.time()-terminal['finished_unix']
   expected_events.append(dict(type=type(e).__name__,message=str(e),observed_unix=time.time(),terminal_detection_delay_seconds=elapsed));passed=elapsed<3
  else:errors.append(dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc(),unix_time=time.time()))
 finally:
  if read_log is not None:read_log.close()
  forbidden=[n for n in sys.modules if n=='torch' or n.startswith('torch.') or n=='src' or n.startswith('src.') or n.startswith('transformers')]
  if forbidden:passed=False;errors.append(dict(type='ForbiddenImport',message=str(forbidden)))
  result=dict(passed=passed,CPU_only=True,model_loaded=False,checkpoint_loaded=False,CUDA_forward=False,forbidden_modules=forbidden,purpose=purpose,expected_negative_condition_detected=bool(expected_events),expected_events=expected_events,reads=reads,unique_realtime_samples=len(seqs),sequences=sorted(seqs),errors=errors,first_record=first,last_record=last,producer_terminal=terminal,monitor_session_id=session,consumer_pid=os.getpid(),started_unix=started,duration_seconds=time.time()-started,consumer_exit_code=0 if passed else 2,finished_unix=time.time())
  write_new(root/'consumer_result.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ['first_record','last_record','producer_terminal']}),flush=True)
 return result['consumer_exit_code']
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--session',required=True);p.add_argument('--purpose',choices=['concurrency','expect-init-failure','expect-stop'],required=True);a=p.parse_args();sys.exit(consume(a.root,a.session,a.purpose))
