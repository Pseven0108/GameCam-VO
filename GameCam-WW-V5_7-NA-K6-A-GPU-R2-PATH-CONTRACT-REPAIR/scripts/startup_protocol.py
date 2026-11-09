"""Bounded preparation and CUDA readiness; status is never CUDA telemetry."""
import math,os,pathlib,threading,time
from linux_safety import SafetyStop,atomic_json,append_json,read_json,MAX_AGE,EXPECTED_UUID
PROTOCOL='gamecam-startup-phases-v1'
STARTUP_SECONDS=15.0
PHASES=('WORKER_IMPORTING','CUDA_INITIALIZING','CUDA_CONTEXT_READY','CUDA_MONITOR_READY','WORKER_READY')

class StartupReporter:
    def __init__(self,out,session):
        self.out=pathlib.Path(out);self.session=session;self.phase=PHASES[0];self.cuda_started=None;self.seq=0;self.failure=None
        self.stop=threading.Event();self.lock=threading.Lock();self.thread=threading.Thread(target=self.run,name='worker-startup-status',daemon=True)
    def start(self):
        self.publish();self.thread.start();return self
    def set_phase(self,phase):
        with self.lock:
            if phase not in PHASES or PHASES.index(phase)<PHASES.index(self.phase):raise SafetyStop('STARTUP_PHASE_REGRESSION')
            self.phase=phase
            if phase=='CUDA_INITIALIZING' and self.cuda_started is None:self.cuda_started=time.monotonic()
        self.publish()
    def publish(self):
        with self.lock:
            self.seq+=1;x=dict(schema=PROTOCOL,kind='worker_startup',session=self.session,worker_pid=os.getpid(),sample_seq=self.seq,monotonic_time=time.monotonic(),unix_time=time.time(),phase=self.phase,cuda_started_monotonic=self.cuda_started,ok=True)
            append_json(self.out/'worker_startup_samples.jsonl',x);atomic_json(self.out/'worker_startup.latest.json',x)
    def run(self):
        while not self.stop.wait(.2):
            try:self.publish()
            except BaseException as exc:self.failure=str(exc);return
    def finish(self):
        self.stop.set()
        if self.thread.is_alive():self.thread.join(timeout=3)
        if self.thread.is_alive():raise SafetyStop('STARTUP_REPORTER_THREAD_NOT_STOPPED')

class StartupGate:
    def __init__(self,worker_start,pid,session):
        self.worker_start=worker_start;self.pid=pid;self.session=session;self.last=None;self.cuda_start=None
    def observe(self,x,now=None):
        now=time.monotonic() if now is None else now
        if x.get('schema')!=PROTOCOL or x.get('kind')!='worker_startup' or x.get('session')!=self.session or x.get('worker_pid')!=self.pid or x.get('ok') is not True:raise SafetyStop('STARTUP_STATUS_IDENTITY_INVALID')
        seq=x.get('sample_seq');stamp=x.get('monotonic_time');phase=x.get('phase');cs=x.get('cuda_started_monotonic')
        if type(seq) is not int or seq<1 or type(stamp) not in (int,float) or not math.isfinite(stamp) or stamp<self.worker_start or stamp>now+1 or phase not in PHASES:raise SafetyStop('STARTUP_STATUS_INVALID')
        if now-stamp>MAX_AGE:raise SafetyStop('WORKER_STARTUP_HEARTBEAT_STALE_OVER_3_SECONDS')
        if self.last:
            if seq<self.last['sample_seq'] or stamp<self.last['monotonic_time'] or PHASES.index(phase)<PHASES.index(self.last['phase']):raise SafetyStop('STARTUP_STATUS_ROLLBACK')
            if seq==self.last['sample_seq'] and x!=self.last:raise SafetyStop('STARTUP_STATUS_SAME_SEQUENCE_DRIFT')
            if seq>self.last['sample_seq'] and stamp<=self.last['monotonic_time']:raise SafetyStop('STARTUP_STATUS_TIME_NOT_ADVANCING')
        if cs is not None:
            if type(cs) not in (int,float) or not math.isfinite(cs) or cs<self.worker_start or cs>stamp or phase==PHASES[0]:raise SafetyStop('CUDA_START_MARKER_INVALID')
            if cs-self.worker_start>STARTUP_SECONDS:raise SafetyStop('WORKER_PREPARATION_TIMEOUT_15_SECONDS')
            if self.cuda_start is not None and cs!=self.cuda_start:raise SafetyStop('CUDA_START_MARKER_CHANGED')
            self.cuda_start=cs
        elif phase!=PHASES[0] or self.cuda_start is not None:raise SafetyStop('CUDA_START_MARKER_MISSING')
        self.last=dict(x)
    def check_deadline(self,now=None):
        now=time.monotonic() if now is None else now
        if self.last and now-self.last['monotonic_time']>MAX_AGE:raise SafetyStop('WORKER_STARTUP_HEARTBEAT_STALE_OVER_3_SECONDS')
        if self.cuda_start is None:
            if now-self.worker_start>STARTUP_SECONDS:raise SafetyStop('WORKER_PREPARATION_TIMEOUT_15_SECONDS')
        elif now-self.cuda_start>STARTUP_SECONDS:raise SafetyStop('CUDA_STARTUP_BARRIER_TIMEOUT')
    def check_cuda(self,sample):
        if self.cuda_start is None or self.last is None or PHASES.index(self.last['phase'])<PHASES.index('CUDA_CONTEXT_READY'):raise SafetyStop('CUDA_SAMPLE_BEFORE_CONTEXT_READY')
        if sample['monotonic_time']<self.cuda_start:raise SafetyStop('CUDA_SAMPLE_PREDATES_INITIALIZATION')

def validate_permit(permit,session,execution_kind):
    if permit.get('session')!=session or permit.get('execution_kind')!=execution_kind:raise SafetyStop('MODEL_STARTUP_PERMIT_INVALID')
    if execution_kind=='cpu_dummy':
        if permit.get('cpu_dummy_only') is not True or permit.get('model_execution_authorized') is not False:raise SafetyStop('SYNTHETIC_STARTUP_PERMIT_INVALID')
    elif execution_kind in {'droidw','droidw_diagnostic'}:
        if permit.get('model_execution_authorized') is not True:raise SafetyStop('MODEL_STARTUP_PERMIT_INVALID')
        if execution_kind=='droidw_diagnostic' and permit.get('diagnostic_only') is not True:raise SafetyStop('DIAGNOSTIC_PERMIT_KIND_INVALID')
    else:raise SafetyStop('STARTUP_EXECUTION_KIND_INVALID')
