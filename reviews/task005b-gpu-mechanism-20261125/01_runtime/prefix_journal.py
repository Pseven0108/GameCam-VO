"""Read-only replay of a sealed historical schedule; no decisions regenerated."""
import json,gzip,copy,hashlib
from pathlib import Path
from control_common import ControlError,canonical,digest
from native_control.runtime import NativeJournal,SCHEMA
from native_control.stages import schedule_scope
class ReadOnlyPrefixJournal:
 def __init__(self,source,output,expected_sha,stop_rgb=401):
  self.path=Path(source);self.output=Path(output);self.stop_rgb=stop_rgb
  h=hashlib.sha256()
  with self.path.open('rb') as f:
   for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
  if h.hexdigest()!=expected_sha:raise ControlError('Frozen schedule file SHA differs')
  self.file=gzip.open(self.path,'rt') if self.path.suffix=='.gz' else self.path.open()
  row=json.loads(next(self.file));self.header=row['header'];self.stage=schedule_scope(self.header);self.max_rgb=487
  self.previous=digest(self.header)
  if row.get('schema')!=SCHEMA or row.get('sha256')!=self.previous or self.stage!='formal487':raise ControlError('Frozen schedule header differs')
  self.index=0;self.failed=False;self.open_frame=None;self.last_frame=18;self.open_operations=[]
  self.log=self.output.open('x',buffering=1)
 def point(self,kind,rgb,context,payload,select=False):
  try:
   e=json.loads(next(self.file))
   if (e.get('type'),e.get('index'),e.get('previous_sha256'))!=('event',self.index,self.previous):raise ControlError('Frozen schedule chain/order mismatch')
   if e['sha256']!=digest({k:v for k,v in e.items() if k!='sha256'}):raise ControlError('Frozen schedule event hash mismatch')
   if (e['kind'],e['rgb'],e['context'])!=(kind,rgb,context):raise ControlError('Frozen schedule context mismatch at '+str(self.index))
   if select:payload=copy.deepcopy(e['payload'])
   elif payload!=e['payload']:raise ControlError('Frozen schedule nondecision payload mismatch at '+str(self.index))
   NativeJournal._lifecycle(self,kind,rgb,payload)
   self.log.write(json.dumps({'index':self.index,'kind':kind,'rgb':rgb,'source_sha256':e['sha256'],'context_sha256':digest(context),'payload':payload},sort_keys=True)+'\n')
   self.previous=e['sha256'];self.index+=1;return payload
  except BaseException:self.failed=True;raise
 def finish_prefix(self):
  if self.failed or self.open_frame is not None or self.open_operations or self.last_frame!=self.stop_rgb:raise ControlError('Incomplete prefix lifecycle')
  self.log.close();self.file.close()
  return {'consumed_events':self.index,'last_source_event_sha256':self.previous,'last_rgb':self.last_frame,'source_schedule_header':self.header,'partial_prefix_only':True,'full487_completed':False}
