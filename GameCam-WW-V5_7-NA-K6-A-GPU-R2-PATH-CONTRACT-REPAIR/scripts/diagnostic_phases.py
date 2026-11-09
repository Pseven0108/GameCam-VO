"""Low-overhead initialization events. No model import or CUDA synchronization."""
import contextlib, json, os, pathlib, time
from linux_safety import append_json, read_json, validate_sample, SafetyStop
DIAGNOSTIC_TYPE='BOUNDED_MODEL_DIAGNOSTIC'
STOP_PHASE='TRACKER_CONSTRUCTION_DONE'
class ControlledDiagnosticStop(BaseException):
    pass
class PhaseRecorder:
    def __init__(self, output, session_dir, session, stop_phase=STOP_PHASE, torch=None):
        if stop_phase != STOP_PHASE: raise SafetyStop('DIAGNOSTIC_STOP_SCOPE_INVALID')
        self.path=pathlib.Path(output)/'startup_phase_events.jsonl'
        self.session_dir=pathlib.Path(session_dir); self.session=session
        self.stop_phase=stop_phase; self.torch=torch; self.start=time.monotonic()
        self.events=[]; self.loaded_weights=set(); self.stopped=False; self.error_reporting_failures=[]
    def resource(self):
        t=self.torch; cuda=None; nvml=None
        if t is not None and t.cuda.is_initialized():
            free,total=t.cuda.mem_get_info()
            cuda=dict(cuda_free_MiB=free/1048576,cuda_total_MiB=total/1048576,
                allocated_MiB=t.cuda.memory_allocated()/1048576,reserved_MiB=t.cuda.memory_reserved()/1048576,
                peak_allocated_MiB=t.cuda.max_memory_allocated()/1048576,
                peak_reserved_MiB=t.cuda.max_memory_reserved()/1048576)
            if cuda['cuda_free_MiB']<512: raise SafetyStop('CUDA_FREE_BELOW_512_MiB')
        p=self.session_dir/'nvml.latest.json'
        if p.exists():
            nvml=read_json(p); validate_sample(nvml,'nvml',self.session)
        rss=int(pathlib.Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        return dict(cuda=cuda,nvml=nvml,worker_RSS_bytes=rss,
            cuda_status='SAMPLED' if cuda is not None else 'CONTEXT_NOT_INITIALIZED')
    def emit(self,phase,edge='point',elapsed_ms=0,error=None,**detail):
        now=time.monotonic()
        row=dict(event='STARTUP_PHASE_EVENT',session=self.session,monotonic_time=now,
            unix_time=time.time(),worker_pid=os.getpid(),phase=phase,edge=edge,
            elapsed_ms=elapsed_ms,since_process_ms=(now-self.start)*1000,exception=error,
            **self.resource(),**detail)
        append_json(self.path,row); self.events.append(row); return row
    @contextlib.contextmanager
    def span(self,phase):
        start=time.monotonic(); self.emit(phase,'start')
        try: yield
        except BaseException as exc:
            try:self.emit(phase,'error',(time.monotonic()-start)*1000,error=str(exc) or type(exc).__name__)
            except BaseException as telemetry_error:
                self.error_reporting_failures.append(dict(phase=phase,primary_failure=str(exc),secondary_reporting_failure=str(telemetry_error)))
            raise
        else: self.emit(phase,'end',(time.monotonic()-start)*1000)
    def dependency_event(self,event):
        if event.get('event')=='weight_load_completed': self.loaded_weights.add(event['dependency_id'])
        self.emit('DEPENDENCY_LOADER','point',dependency_event=event)
    def checkpoint(self,phase):
        self.emit(phase)
        if phase==self.stop_phase:
            if len(self.loaded_weights)!=4: raise SafetyStop('DIAGNOSTIC_NOT_ALL_FOUR_WEIGHTS_LOADED')
            self.stopped=True
            self.emit('CONTROLLED_DIAGNOSTIC_STOP',stop_after_phase=phase,
                real_frame_submission=False,tracker_run_called=False,ba_executed=False)
            raise ControlledDiagnosticStop(phase)
