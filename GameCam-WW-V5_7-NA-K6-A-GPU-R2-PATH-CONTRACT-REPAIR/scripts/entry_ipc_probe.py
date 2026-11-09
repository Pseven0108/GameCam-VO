"""Real Python3.10 fork/spawn IPC tests, never model execution."""
import argparse,gc,json,os,pathlib,subprocess,sys,time,traceback
from ipc_runtime import IPCPolicy,prepare_owner,cleanup_owner
from model_io_boundary_v2 import ModelIOBoundary
from linux_safety import atomic_json

def install(d,sid,fallback):
 p=IPCPolicy('/dev/shm/gamecam-ipc/'+sid,str(d/'tmp'),sid,d);p.install_arena(force_fallback=fallback)
 b=ModelIOBoundary([],list(pathlib.Path(__file__).parent.glob('*.py')),[],[d/'model'],[sys.prefix],ipc_policy=p,worker_files=[d/'ipc_worker_events.jsonl'],worker_root=d);b.install();return p,b

def participant(value,array,raw,rawarray,lock,rlock,q,conn,go,d,sid,fallback,mode):
 if __import__('multiprocessing').get_start_method()=='spawn': install(pathlib.Path(d),sid,fallback)
 conn.send({'stage':'ready','pid':os.getpid()});assert go.wait(10)
 for _ in range(100):
  with lock: value.value+=1;array[1]+=2
  with rlock:
   with rlock: raw.value+=3;rawarray[0]+=4
 q.put({'pid':os.getpid(),'ok':True});q.close();q.join_thread();conn.send(os.getpid());conn.close()
 if mode=='abnormal':os._exit(7)
 if mode=='terminate':
  while True:time.sleep(.1)

def worker(a):
 import multiprocessing as mp
 d=pathlib.Path(a.directory);p,b=install(d,a.session,a.fallback);ctx=mp.get_context(a.method)
 fd0=len(list(pathlib.Path('/proc/self/fd').iterdir()));v=ctx.Value('i',0);arr=ctx.Array('i',[0,0]);rv=ctx.RawValue('i',0);ra=ctx.RawArray('i',[0,0]);lock=ctx.Lock();rlock=ctx.RLock();q=ctx.Queue();go=ctx.Event();children=[];pending=[]
 for _ in range(2 if a.mode=='normal' else 1):
  recv,send=ctx.Pipe(False);child=ctx.Process(target=participant,args=(v,arr,rv,ra,lock,rlock,q,send,go,str(d),a.session,a.fallback,a.mode));child.start();send.close();pending.append((child,recv))
 for child,recv in pending:
  assert recv.poll(10);assert recv.recv()['stage']=='ready';assert child.is_alive()
 go.set()
 for child,recv in pending:
  assert recv.poll(10);pid=recv.recv();recv.close();assert q.get(timeout=10)['ok']
  if a.mode=='terminate':child.terminate()
  child.join(10);assert not child.is_alive();assert child.exitcode=={'normal':0,'abnormal':7,'terminate':-15}[a.mode];children.append({'pid':pid,'exitcode':child.exitcode});child.close()
 n=len(children);assert [v.value,arr[1],rv.value,ra[0]]==[100*n,200*n,300*n,400*n]
 q.close();q.join_thread();counts=[];maps=[]
 for _ in range(20):
  z=ctx.Value('i',1);z.value+=1;assert z.value==2;del z;gc.collect();counts.append(len(list(pathlib.Path('/proc/self/fd').iterdir())));maps.append(sum('pym-' in x for x in pathlib.Path('/proc/self/maps').read_text().splitlines()))
 assert max(counts)-min(counts)<=2;assert max(maps)-min(maps)<=1
 report={'passed':True,'pid':os.getpid(),'method':a.method,'fallback':a.fallback,'mode':a.mode,'checks':['Value','Array','RawValue','RawArray','Lock','RLock','Process','Pipe','Queue','parent_child_roundtrip','two_live_children_released_by_shared_event_and100_locked_updates' if n==2 else a.mode],'children':children,'fd_before':fd0,'fd_cycles':counts,'arena_map_cycles':maps,'ipc_events':list(p.events),'active_children':len(mp.active_children()),'arena_files_live':[str(x) for x in pathlib.Path(p.root).iterdir() if x.name!='.gamecam-session.json'],'fallback_files_live':[str(x) for x in p.fallback.iterdir()],'python':sys.version,'boundary_installed':True,'native_sem_lock_note':'Native POSIX semaphores are not mediated by Python file audit events; per-process cleanup separately checked.'}
 assert report['active_children']==0
 atomic_json(d/'model/report.json',report)

def main(a):
 if a.worker:return worker(a)
 out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=False);results=[];parent_fd=[];shm0=set(pathlib.Path('/dev/shm').iterdir());started=time.monotonic()
 cases=[(r,m,f,'normal') for r in range(20) for m in ('fork','spawn') for f in (False,True)]+[(20,m,f,x) for m in ('fork','spawn') for f in (False,True) for x in ('abnormal','terminate')]
 for i,(rnd,method,fallback,mode) in enumerate(cases):
  sid='K6A_ENTRY_IPC_'+str(os.getpid())+'_'+str(i);d=out/str(i);d.mkdir(mode=0o700);(d/'model').mkdir(mode=0o700);owner=prepare_owner(d,sid)
  cmd=[sys.executable,'-B',__file__,'--worker','--directory',str(d),'--session',sid,'--method',method,'--mode',mode]+(['--fallback'] if fallback else [])
  t=time.monotonic();p=subprocess.run(cmd,capture_output=True,text=True,timeout=35);(d/'stdout.txt').write_text(p.stdout);(d/'stderr.txt').write_text(p.stderr)
  try:
   assert p.returncode==0,p.stderr;report=json.loads((d/'model/report.json').read_text());cleanup=cleanup_owner(owner,True,True,[report['pid']]+[c['pid'] for c in report['children']]);assert cleanup['passed'];assert not (pathlib.Path('/proc')/str(report['pid'])).exists()
   row={'passed':True,'index':i,'round':rnd,'method':method,'fallback':fallback,'mode':mode,'seconds':time.monotonic()-t,'fd_range':max(report['fd_cycles'])-min(report['fd_cycles']),'mmap_range':max(report['arena_map_cycles'])-min(report['arena_map_cycles']),'cleanup':cleanup}
  except Exception as e:row={'passed':False,'index':i,'error':str(e),'traceback':traceback.format_exc()}
  results.append(row);parent_fd.append(len(list(pathlib.Path('/proc/self/fd').iterdir())))
  if not row['passed']:break
 remaining=[str(x) for x in set(pathlib.Path('/dev/shm').iterdir())-shm0];report={'status':'PASS' if len(results)==88 and all(x['passed'] for x in results) and not remaining else 'FAIL','cases':results,'repeated_normal_rounds_per_method_and_mode':20,'case_count':len(results),'parent_fd_counts':parent_fd,'parent_fd_growth':max(parent_fd)-min(parent_fd),'new_shm_entries_after_all_process_exit':remaining,'seconds':time.monotonic()-started,'real_model_attempts':0,'checkpoint_deserialized':False,'GT_values_read':False,'python':sys.version}
 (out/'PYTHON_IPC_INTEGRATION_REPORT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='cases'}));return 0 if report['status']=='PASS' else 2
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--directory');p.add_argument('--session');p.add_argument('--method');p.add_argument('--mode');p.add_argument('--fallback',action='store_true');p.add_argument('--output');a=p.parse_args();raise SystemExit(main(a))
