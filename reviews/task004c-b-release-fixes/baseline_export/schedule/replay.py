"""Strict recorded-event selection with pre/post discrete-state checks."""
import copy,json,pathlib
from control_common import ControlError,digest
from schedule.schema import validate_payload,validate_context,EventLifecycle

def load_schedule(path,expected_identity=None):
    try:rows=[json.loads(s) for s in pathlib.Path(path).read_text().splitlines()]
    except Exception as e:raise ControlError('Unreadable JSONL') from e
    if len(rows)<2 or rows[0].get('type')!='header' or rows[-1].get('type')!='footer':raise ControlError('Unsealed schedule')
    h=rows[0];header=h['header'];prev=digest(header)
    if h['sha256']!=prev or header.get('init_D')!=0 or header.get('W')!=1 or header.get('U')!=1:raise ControlError('Invalid schedule header')
    if header.get('schedule') not in ('S0','S1') or header.get('producer_D')!={'S0':0,'S1':1}[header.get('schedule')]:raise ControlError('Producer mismatch')
    for k,v in (expected_identity or {}).items():
        if header.get(k)!=v:raise ControlError('Schedule identity mismatch: '+k)
    events=rows[1:-1];lifecycle=EventLifecycle()
    for i,e in enumerate(events):
        if e.get('type')!='event' or e['event_index']!=i or e['previous_sha256']!=prev or e['sha256']!=digest({k:v for k,v in e.items() if k!='sha256'}):raise ControlError('Schedule chain/order mismatch')
        validate_payload(e['event_type'],e['payload']);lifecycle.accept(e['frame_id'],e['event_type'],e['payload'])
        if validate_context(e['context_before'])!=e['before_sha256'] or validate_context(e['context_after'])!=e['after_sha256']:raise ControlError('Context digest mismatch')
        if i and events[i-1]['context_after']!=e['context_before']:raise ControlError('Disconnected event contexts')
        prev=e['sha256']
    if rows[-1]!=dict(type='footer',event_count=len(events),last_sha256=prev):raise ControlError('Bad sealed footer')
    lifecycle.finish()
    return {'header':header,'events':events,'last_sha256':prev}

def validate_schedule(path,expected_identity=None):
    s=load_schedule(path,expected_identity)
    return {'valid':True,'events':len(s['events']),'last_sha256':s['last_sha256'],'native_cross_D_verified':False}

class ScheduleReplayer:
    def __init__(self,schedule):self.schedule=schedule;self.index=0;self.pending=None;self.failed=False
    def select(self,event_type,frame_id,current_context):
        if self.failed or self.pending is not None:raise ControlError('Replay stopped/pending confirmation')
        try:
            e=self.schedule['events'][self.index]
            if (e['event_type'],e['frame_id'])!=(event_type,frame_id) or validate_context(current_context)!=e['before_sha256']:raise ControlError('Replay event incompatible at %d'%self.index)
            self.pending=e
            # Only discrete control payloads are exposed. No recorded tensor values.
            return copy.deepcopy(e['payload'])
        except BaseException as e:
            self.failed=True
            if isinstance(e,IndexError):raise ControlError('Schedule exhausted') from e
            raise
    def confirm(self,actual_context):
        try:
            if self.failed or self.pending is None or validate_context(actual_context)!=self.pending['after_sha256']:raise ControlError('Replay result mismatch at %d'%self.index)
            self.index+=1;self.pending=None
        except BaseException:self.failed=True;raise
    def finish(self):
        if self.failed or self.pending is not None or self.index!=len(self.schedule['events']):raise ControlError('Incomplete/failed replay')
        return True

def replay_schedule(path,handler,expected_identity=None):
    r=ScheduleReplayer(load_schedule(path,expected_identity))
    while r.index<len(r.schedule['events']):
        e=r.schedule['events'][r.index];p=r.select(e['event_type'],e['frame_id'],handler.context())
        handler.apply(e['event_type'],p);r.confirm(handler.context())
    r.finish();return r
