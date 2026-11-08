"""CPU-only append log reader, startup barrier and producer terminal detection."""
import json,math,threading,time
from pathlib import Path
MAX_AGE=3.0;FUTURE_TOLERANCE=1.0;SAMPLE_PERIOD=0.25
class MonitorError(RuntimeError):pass
class MonitorNotReady(MonitorError):pass
class MonitorCompleted(MonitorError):pass
class MonitorReader:
 def __init__(self,path,session):
  self.path=Path(path);self.session=session;self.previous=None;self.lock=threading.RLock();self.exit_path=self.path.with_name('windows_monitor.exit.json')
 def terminal(self,allow_completed=False):
  if not self.exit_path.exists():return None
  try:x=json.loads(self.exit_path.read_text(encoding='utf-8-sig'))
  except (OSError,ValueError) as e:raise MonitorError('PRODUCER_EXIT_RECORD_UNREADABLE:'+str(e)) from e
  if x.get('monitor_session_id')!=self.session:raise MonitorError('PRODUCER_EXIT_SESSION_MISMATCH')
  status=x.get('exit_status')
  if status=='COMPLETED' and allow_completed:return x
  if status=='COMPLETED':raise MonitorCompleted('PRODUCER_COMPLETED_BEFORE_STARTUP')
  if status not in ['FAILED_INITIALIZATION','FAILED_RUNTIME','STOPPED']:raise MonitorError('PRODUCER_INVALID_EXIT_STATUS:'+str(status))
  raise MonitorError('PRODUCER_EXIT_'+status+':'+str(x.get('error_message','')))
 def records(self,limit=2):
  try:
   with self.path.open('rb') as f:
    f.seek(0,2);size=f.tell();start=max(0,size-65536);f.seek(start);data=f.read()
  except OSError as e:raise MonitorNotReady('MONITOR_LOG_UNREADABLE:'+str(e)) from e
  rows=data.split(b'\n')[:-1]
  if start and rows:rows=rows[1:]
  rows=[v for v in rows if v.strip()]
  if not rows:raise MonitorNotReady('MONITOR_NO_COMPLETE_RECORD')
  try:return [json.loads(v.decode('utf-8-sig')) for v in rows[-limit:]]
  except (ValueError,UnicodeError) as e:raise MonitorError('MONITOR_INVALID_COMPLETE_JSON:'+str(e)) from e
 def validate(self,x,now=None):
  now=time.time() if now is None else now
  if x.get('monitor_session_id')!=self.session:raise MonitorError('MONITOR_SESSION_MISMATCH')
  seq=x.get('sample_seq');ts=x.get('unix_time')
  if type(seq) is not int or seq<1:raise MonitorError('MONITOR_INVALID_SAMPLE_SEQ')
  if type(ts) not in (int,float) or not math.isfinite(ts) or ts<=0:raise MonitorError('MONITOR_INVALID_TIME')
  if now-ts>MAX_AGE:raise MonitorError('MONITOR_STALE_OVER_3_SECONDS')
  if ts-now>FUTURE_TOLERANCE:raise MonitorError('MONITOR_FUTURE_TIMESTAMP')
  if x.get('available') is not True:raise MonitorError('MONITOR_UNAVAILABLE:'+str(x.get('error','')))
  if x.get('anomaly'):raise MonitorError('WINDOWS_ANOMALY:'+str(x['anomaly']))
  if x.get('desktop_shell_healthy') is not True:raise MonitorError('WINDOWS_SHELL_UNRESPONSIVE')
  dxgi=x.get('dxgi_adapters');adapters=x.get('adapters')
  if not isinstance(dxgi,list) or not dxgi or not isinstance(adapters,list) or not adapters:raise MonitorError('MONITOR_DXGI_OR_ADAPTER_MISSING')
  local=dxgi[0].get('Local',{})
  if local.get('HResult')!=0 or type(local.get('BudgetBytes')) not in (int,float) or local['BudgetBytes']<=0:raise MonitorError('MONITOR_DXGI_INVALID')
  return x
 def read_last(self,allow_completed=False):
  with self.lock:
   self.terminal(allow_completed=allow_completed);x=self.validate(self.records(1)[-1]);p=self.previous
   if p:
    if x['sample_seq']<p['sample_seq']:raise MonitorError('MONITOR_SAMPLE_SEQ_ROLLBACK')
    if x['unix_time']<p['unix_time']:raise MonitorError('MONITOR_TIMESTAMP_ROLLBACK')
    if x['sample_seq']==p['sample_seq'] and x['unix_time']!=p['unix_time']:raise MonitorError('MONITOR_SAME_SEQ_CHANGED_TIME')
    if x['sample_seq']>p['sample_seq'] and x['unix_time']<=p['unix_time']:raise MonitorError('MONITOR_NONINCREASING_TIME')
   self.previous=x;return x
 def startup_pair(self):
  with self.lock:
   self.terminal();rows=self.records()
   if len(rows)<2:raise MonitorNotReady('MONITOR_NEEDS_TWO_RECORDS')
   a,b=[self.validate(v) for v in rows[-2:]]
   if b['sample_seq']<=a['sample_seq']:raise MonitorError('MONITOR_STARTUP_SEQ_NOT_INCREASING')
   if b['unix_time']-a['unix_time']<SAMPLE_PERIOD:raise MonitorError('MONITOR_STARTUP_INTERVAL_BELOW_SAMPLE_PERIOD')
   self.previous=b;return [a,b]
def await_startup(reader,is_alive=lambda:True,timeout=15):
 begin=time.monotonic();last=None
 while time.monotonic()-begin<timeout:
  reader.terminal()
  if not is_alive():raise MonitorError('MONITOR_PRODUCER_EXITED_BEFORE_STARTUP')
  try:return reader.startup_pair()
  except MonitorNotReady as e:last=str(e)
  time.sleep(.02)
 raise MonitorError('MONITOR_STARTUP_TIMEOUT:'+str(last))
