"""Production single-run supervisor and guards; integration fixtures use the same IPC/process path."""
import datetime,json,math,os,pathlib,signal,subprocess,time
from collections import deque
from linux_safety import SafetyStop,validate_sample,atomic_json,append_json,read_json,EXPECTED_UUID,NVML_PERIOD,SUPERVISOR_PERIOD
GROWTH_WINDOW=30;GROWTH_MIN_MIB=512;MAX_STARTUP_SECONDS=15
class GrowthGuard:
    def __init__(self): self.values=deque(maxlen=30);self.next_ordinal=0
    def append(self,ordinal,allocated):
        if type(ordinal) is not int or ordinal!=self.next_ordinal:raise SafetyStop('FRAME_ORDINAL_SEQUENCE_ERROR')
        if type(allocated) not in (int,float) or not math.isfinite(allocated) or allocated<0:raise SafetyStop('INVALID_FRAME_ALLOCATED')
        self.next_ordinal+=1;self.values.append(float(allocated))
        if len(self.values)==30:
            v=list(self.values)
            if v[-1]-v[0]>512 and all(b>a for a,b in zip(v,v[1:])):raise SafetyStop('SUSTAINED_MONOTONIC_ALLOCATED_GROWTH_30_FRAMES_512_MiB')
        return True
class SampleReader:
    def __init__(self,session):self.session=session;self.previous={}
    def check(self,sample,kind):
        validate_sample(sample,kind,self.session)
        if kind=='cuda' and sample.get('gpu_uuid')!=EXPECTED_UUID:raise SafetyStop('CUDA_GPU_UUID_DRIFT')
        old=self.previous.get(kind)
        if old:
            if sample['sample_seq']<old['sample_seq'] or sample['monotonic_time']<old['monotonic_time']:raise SafetyStop('MONITOR_ROLLBACK')
            if sample['sample_seq']==old['sample_seq'] and sample['monotonic_time']!=old['monotonic_time']:raise SafetyStop('MONITOR_SAME_SEQ_CHANGED_TIME')
            if sample['sample_seq']>old['sample_seq'] and sample['monotonic_time']<=old['monotonic_time']:raise SafetyStop('MONITOR_NONINCREASING_TIME')
        self.previous[kind]=dict(sample);return sample

def stop_owned(process,reason,out,label,kind):
    start=time.monotonic();sent=[]
    if process.poll() is None:
        try:os.killpg(process.pid,signal.SIGTERM);sent.append('SIGTERM')
        except ProcessLookupError:pass
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);sent.append('SIGKILL');process.wait(timeout=5)
    r={'reason':reason,'pid':process.pid,'signals':sent,'exit_code':process.poll(),'fully_exited':process.poll() is not None,'signal_to_exit_seconds':time.monotonic()-start,'SIGTERM_grace_seconds':5,'execution_kind':kind}
    atomic_json(pathlib.Path(out)/(label+'_stop.json'),r);return r

def supervise_once(out,session,worker_command,monitor_command,kind,env=None,expected_frames=None,launch_context=None,ipc_for_cpu_tests=False):
    """One launch; active CUDA freshness stays 3s; terminal cleanup has its own 5s bound."""
    from worker_terminal import read_terminal,TERMINAL_CLEANUP_SECONDS
    if kind not in {'cpu_dummy','droidw','droidw_diagnostic'}:raise ValueError('Disallowed execution kind')
    if kind in {'droidw','droidw_diagnostic'}:
        if launch_context is None:raise SafetyStop('DROIDW_LAUNCH_CONTEXT_REQUIRED')
        launch_context.validate(out,session,worker_command,monitor_command,env or os.environ,consume=False)
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=False,mode=0o700);os.chmod(out,0o700)
    reader=SampleReader(session);growth=GrowthGuard();worker=None;monitor=None;reason=None;frame_offset=0;frame_buffer='';first_nvml=None;first_cuda=None;permit=False;startup_complete=False;events=[];handles=[];start=time.monotonic();stop_record=None
    terminal=None;terminal_seen=None;primary_failure=None;cleanup_reason=None;ipc_owner=None;ipc_cleanup=None
    def event(state,**kw):
        row={'monotonic_time':time.monotonic(),'unix_time':time.time(),'session':session,'state':state,'execution_kind':kind,**kw};events.append(row);append_json(out/'supervisor_heartbeat.jsonl',row)
    def check_monitor():
        if monitor.poll() is not None:raise SafetyStop('MONITOR_SUBPROCESS_EXITED:'+str(monitor.returncode))
        n=reader.check(read_json(out/'nvml.latest.json'),'nvml')
        if kind in {'droidw','droidw_diagnostic'}:
            allowed_pid=worker.pid if worker is not None else None
            if any(p['pid']!=allowed_pid for p in n['gpu_processes']):raise SafetyStop('UNKNOWN_GPU_COMPUTE_PROCESS')
        return n
    def consume_frames():
        nonlocal frame_offset,frame_buffer
        p=out/'frame_samples.jsonl'
        if not p.exists():return
        with p.open() as f:f.seek(frame_offset);chunk=f.read();frame_offset=f.tell()
        frame_buffer+=chunk;records=frame_buffer.split('\n');frame_buffer=records.pop()
        for line in records:
            if not line:continue
            x=json.loads(line);validate_sample(x,'cuda',session)
            if x.get('gpu_uuid')!=EXPECTED_UUID:raise SafetyStop('FRAME_GPU_UUID_DRIFT')
            if x.get('worker_pid')!=worker.pid:raise SafetyStop('FRAME_WORKER_PID_MISMATCH')
            append_json(out/'supervisor_consumed_frames.jsonl',x);growth.append(x['frame_ordinal'],x['allocated_MiB'])
    def observe_terminal():
        nonlocal terminal,terminal_seen,primary_failure
        if terminal is not None:return True
        candidate=read_terminal(out,session,worker.pid,kind)
        if candidate is None:return False
        terminal=candidate;terminal_seen=time.monotonic();primary_failure=candidate.get('primary_failure')
        event('WORKER_TERMINAL_RESULT',primary_failure=primary_failure,result_sha256=candidate['result_sha256'])
        event('WORKER_TERMINAL_CLEANUP',cleanup_deadline_seconds=TERMINAL_CLEANUP_SECONDS)
        return True
    try:
        def open_log(name):
            fd=os.open(str(out/name),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            return os.fdopen(fd,'w',encoding='utf-8')
        handles=[open_log(n) for n in ['monitor.stdout.txt','monitor.stderr.txt','worker.stdout.txt','worker.stderr.txt']]
        event('MONITOR_STARTING',command=monitor_command)
        monitor=subprocess.Popen(monitor_command,stdout=handles[0],stderr=handles[1],env=env,start_new_session=True)
        while True:
            if monitor.poll() is not None:raise SafetyStop('MONITOR_SUBPROCESS_EXITED:'+str(monitor.returncode))
            if time.monotonic()-start>MAX_STARTUP_SECONDS:raise SafetyStop('NVML_STARTUP_BARRIER_TIMEOUT')
            if (out/'nvml.latest.json').is_file():
                n=check_monitor()
                if first_nvml is None:first_nvml=n
                if n['sample_seq']>first_nvml['sample_seq'] and n['monotonic_time']-first_nvml['monotonic_time']>=NVML_PERIOD:
                    atomic_json(out/'nvml_startup_barrier.json',{'first':first_nvml,'second':n,'minimum_interval_seconds':NVML_PERIOD,'passed':True});break
            event('WAITING_FOR_NVML_BARRIER');time.sleep(.05)
        if kind in {'droidw','droidw_diagnostic'}:launch_context.validate(out,session,worker_command,monitor_command,env or os.environ,consume=True);event('PRESPAWN_AUTHORIZATION_CLAIMED',candidate_bound=True)
        manifest=getattr(launch_context,'_candidate',None) if launch_context is not None else None
        if (manifest and 'planned_ipc_root' in manifest) or (kind=='cpu_dummy' and ipc_for_cpu_tests):
            from ipc_runtime import prepare_owner
            ipc_owner=prepare_owner(out,session)
            if manifest and ipc_owner['root']!=manifest['planned_ipc_root']:raise SafetyStop('IPC_ROOT_CANDIDATE_MISMATCH')
            event('IPC_ROOT_READY_BEFORE_WORKER',root=ipc_owner['root'])
        worker_start=time.monotonic();event('WORKER_STARTING',command=worker_command)
        worker=subprocess.Popen(worker_command,stdout=handles[2],stderr=handles[3],env=env,start_new_session=True)
        while worker.poll() is None:
            terminal_now=observe_terminal()
            check_monitor()
            if time.monotonic()-start>3600:raise SafetyStop('CONDITION_TIMEOUT_3600_SECONDS')
            if terminal_now:
                consume_frames()
                if time.monotonic()-terminal_seen>=TERMINAL_CLEANUP_SECONDS:raise SafetyStop('WORKER_SHUTDOWN_TIMEOUT')
                event('WORKER_TERMINAL_CLEANUP',worker_pid=worker.pid,elapsed_seconds=time.monotonic()-terminal_seen)
                time.sleep(SUPERVISOR_PERIOD);continue
            if not permit and time.monotonic()-worker_start>MAX_STARTUP_SECONDS:raise SafetyStop('CUDA_STARTUP_BARRIER_TIMEOUT')
            p=out/'cuda.latest.json'
            if p.exists():
                c=reader.check(read_json(p),'cuda')
                if c.get('worker_pid')!=worker.pid:raise SafetyStop('CUDA_WORKER_PID_MISMATCH')
                if first_cuda is None:first_cuda=c
                if not permit and c['sample_seq']>first_cuda['sample_seq']:
                    atomic_json(out/'work.permit.json',{'session':session,'execution_kind':kind,'model_execution_authorized':kind in {'droidw','droidw_diagnostic'},'diagnostic_only':kind=='droidw_diagnostic','cpu_dummy_only':kind=='cpu_dummy','monotonic_time':time.monotonic()});permit=True;startup_complete=True;event('STARTUP_BARRIER_PASSED');event('WORKER_RUNNING')
            elif time.monotonic()-worker_start>MAX_STARTUP_SECONDS:raise SafetyStop('CUDA_STARTUP_BARRIER_TIMEOUT')
            consume_frames();event('RUNNING' if permit else 'WAITING_FOR_CUDA_BARRIER',worker_pid=worker.pid,frame_samples=growth.next_ordinal);time.sleep(SUPERVISOR_PERIOD)
        rc=worker.wait(timeout=5);observe_terminal();consume_frames()
        if kind=='droidw_diagnostic' and terminal is not None:
            launch_context.validate_terminal(out,terminal)
        if terminal is not None and primary_failure:
            cleanup_reason='TERMINAL_FAILURE_EXIT';raise SafetyStop(primary_failure)
        if rc!=0:raise SafetyStop('WORKER_NONZERO_EXIT:'+str(rc))
        if not startup_complete:raise SafetyStop('WORKER_EXIT_BEFORE_STARTUP_BARRIER')
        if kind in {'droidw','droidw_diagnostic'} and manifest and 'planned_ipc_root' in manifest and terminal is None:raise SafetyStop('WORKER_MISSING_TERMINAL_RESULT')
        if frame_buffer:raise SafetyStop('INCOMPLETE_FRAME_EVENT_AT_EXIT')
        if expected_frames is not None and growth.next_ordinal!=expected_frames:raise SafetyStop('COMPLETED_FRAME_COUNT_MISMATCH')
        check_monitor();event('WORKER_EXITED',exit_code=rc)
        if terminal is not None:cleanup_reason='CLEANUP_COMPLETE';event('CLEANUP_COMPLETE')
    except BaseException as exc:
        cleanup_reason=cleanup_reason or str(exc);reason=primary_failure or str(exc);event('STOPPING',reason=reason,supervisor_cleanup_reason=cleanup_reason)
        atomic_json(out/'supervisor_stop.json',{'reason':reason,'primary_failure':primary_failure,'supervisor_cleanup_reason':cleanup_reason,'session':session,'monotonic_time':time.monotonic()})
        if worker is not None:stop_record=stop_owned(worker,str(exc),out,'worker',kind)
    finally:
        if worker is not None and worker.poll() is None:stop_record=stop_owned(worker,reason or 'FINALLY_CLEANUP',out,'worker',kind)
        if monitor is not None and monitor.poll() is None:
            from linux_safety import secure_text
            secure_text(out/'monitor.stop','Stop requested by owning supervisor\n')
            try:monitor.wait(timeout=2)
            except subprocess.TimeoutExpired:stop_owned(monitor,'MONITOR_CLEANUP_TIMEOUT',out,'monitor',kind)
        if ipc_owner is not None:
            from ipc_runtime import cleanup_owner
            try:ipc_cleanup=cleanup_owner(ipc_owner,worker is None or worker.poll() is not None,monitor is None or monitor.poll() is not None,[worker.pid] if worker is not None else [])
            except BaseException as exc:
                ipc_cleanup={'passed':False,'error':str(exc),'events':list(ipc_owner['events'])};cleanup_reason='IPC_CLEANUP_FAILED:'+str(exc);reason=reason or cleanup_reason;event('IPC_CLEANUP_FAILED',reason=cleanup_reason)
        for f in handles:f.close()
    result={'session':session,'execution_kind':kind,'diagnostic_attempts':1 if kind=='droidw_diagnostic' and launch_context is not None and launch_context.claimed else 0,'model_attempts':1 if kind=='droidw' and launch_context is not None and launch_context.claimed else 0,'model_execution_authorized':kind in {'droidw','droidw_diagnostic'},'diagnostic_execution_authorized':kind=='droidw_diagnostic','formal_120_frame_execution_authorized':kind=='droidw','worker_started':worker is not None,'worker_pid':worker.pid if worker is not None else None,'worker_exit_code':worker.poll() if worker is not None else None,'worker_fully_exited':worker is None or worker.poll() is not None,'monitor_pid':monitor.pid if monitor is not None else None,'monitor_exit_code':monitor.poll() if monitor is not None else None,'monitor_fully_exited':monitor is None or monitor.poll() is not None,'reason':reason,'primary_failure':primary_failure,'supervisor_cleanup_reason':cleanup_reason,'terminal_result':terminal,'terminal_cleanup_limit_seconds':TERMINAL_CLEANUP_SECONDS,'ipc_cleanup':ipc_cleanup,'startup_barrier_passed':startup_complete,'work_permit_written':permit,'completed_frame_samples':growth.next_ordinal,'duration_seconds':time.monotonic()-start,'worker_stop':stop_record,'automatic_retries':0,'passed':reason is None and worker is not None and worker.poll()==0 and monitor is not None and monitor.poll()==0 and (ipc_cleanup is None or ipc_cleanup['passed'])}
    atomic_json(out/'supervisor_result.json',result);return result
