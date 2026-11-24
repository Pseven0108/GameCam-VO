"""Append-only, hash-chained JSONL schedule with a mandatory sealed footer."""
import json,os,pathlib
from control_common import ControlError,canonical,digest
from schedule.schema import validate_payload,validate_context,EventLifecycle

class ScheduleRecorder:
    def __init__(self,path,header):
        if header.get('schedule') not in ('S0','S1') or header.get('producer_D')!={'S0':0,'S1':1}[header.get('schedule')]:raise ControlError('Schedule producer mismatch')
        if header.get('init_D')!=0 or header.get('W')!=1 or header.get('U')!=1 or not header.get('c0_sha256'):raise ControlError('Header lacks common initialization/identity')
        self.path=pathlib.Path(path);self.file=self.path.open('xb');self.count=0;self.closed=False;self.lifecycle=EventLifecycle();self.last_context_sha=None
        self.previous=digest(header);self._line({'type':'header','header':header,'sha256':self.previous})
    def _line(self,x):
        self.file.write(canonical(x)+b'\n');self.file.flush();os.fsync(self.file.fileno())
    def append(self,frame_id,event_type,payload,before,after):
        if self.closed:raise ControlError('Sealed recorder')
        try:
            validate_payload(event_type,payload)
            before_sha=validate_context(before);validate_context(after)
            if self.last_context_sha is not None and self.last_context_sha!=before_sha:raise ControlError('Disconnected recorded event context')
            self.lifecycle.accept(frame_id,event_type,payload)
        except BaseException:self.abort();raise
        event={'type':'event','event_index':self.count,'frame_id':frame_id,'event_type':event_type,'payload':payload,
            'context_before':before,'context_after':after,'before_sha256':validate_context(before),'after_sha256':validate_context(after),'previous_sha256':self.previous}
        event['sha256']=digest(event);self._line(event);self.previous=event['sha256'];self.count+=1;self.last_context_sha=event['after_sha256']
        return event
    def seal(self):
        if self.closed:raise ControlError('Already sealed')
        try:self.lifecycle.finish()
        except BaseException:self.abort();raise
        self._line({'type':'footer','event_count':self.count,'last_sha256':self.previous});self.file.close();self.closed=True
    def abort(self):
        if not self.closed:self.file.close();self.closed=True
        # An aborted stream deliberately lacks its footer.

def record_schedule(path,header,events):
    r=ScheduleRecorder(path,header)
    try:
        for e in events:r.append(*e)
        r.seal()
    except BaseException:r.abort();raise
