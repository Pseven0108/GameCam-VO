"""Native discrete-event control. No saved continuous result is replayed."""
import copy
from dataclasses import dataclass
import json
import os
from pathlib import Path
import time

from control_common import ControlError, canonical, digest

SCHEMA='GAMECAM_NATIVE_DISCRETE_SCHEDULE_V2'
_active=None


class PrefixComplete(Exception):
    """An admitted prefix ended; never fall through to Final BA or Filler."""


def set_active(controller):
    global _active
    if _active is not None and controller is not None:raise ControlError('Controller already installed')
    _active=controller


def active():
    return _active if _active is not None else NULL


class NullControl:
    enabled=False
    def motion_decision(self,proposed,force,threshold,score=None):return bool(proposed),bool(force)
    def keyframe_decision(self,drop,**kw):return bool(drop)
    def bad_edge_mask(self,graph,mask):return mask
    def edge_plan(self,graph,es,loop_edges):return es,loop_edges
    def tracker_begin(self,tracker,stream,values):return values
    def frame_begin(self,*args,**kw):pass
    def frame_end(self,*args,**kw):pass
    def initialization_done(self,*args,**kw):pass
    def graph_created(self,*args,**kw):pass
    def init_age_reset(self,*args,**kw):pass
    def final_phase(self,*args,**kw):pass
    def filler_begin(self,*args,**kw):pass
    def filler_end(self,*args,**kw):pass
    def export(self,*args,**kw):pass
    def depth_flag(self,phase,native):return native
NULL=NullControl()


class NativeJournal:
    """Each begin and result is a separate ordered point, supporting nested calls."""
    def __init__(self,path,header,mode='record',source=None):
        self.path=Path(path);self.file=self.path.open('xb');self.mode=mode;self.failed=False;self.index=0
        self.header=copy.deepcopy(header);self.previous=digest(header);self.source=None
        self.open_frame=None;self.last_frame=18;self.open_operations=[]
        if header.get('init_D')!=0 or header.get('W')!=1 or header.get('U')!=1 or header.get('max_rgb')!=80:
            self.file.close();raise ControlError('Native schedule outside bounded scope')
        if mode=='replay':
            self.source=read_schedule(source)
            for k in ('c0_sha256','init_D','W','U','max_rgb','schedule'):
                if self.source['header'][k]!=header[k]:raise ControlError('Schedule header identity mismatch: '+k)
        elif mode!='record':raise ControlError('Unsupported native journal mode')
        self._write({'type':'header','schema':SCHEMA,'header':header,'sha256':self.previous})

    def _write(self,row):
        self.file.write(canonical(row)+b'\n');self.file.flush();os.fsync(self.file.fileno())

    def point(self,kind,rgb,context,payload,*,select=False):
        if self.failed:raise ControlError('Native schedule latched STOP')
        try:
            if type(rgb) is not int or not 0<=rgb<=80:raise ControlError('Native schedule RGB outside 000..080')
            if self.mode=='replay':
                if self.index>=len(self.source['events']):raise ControlError('Replay stream exhausted')
                e=self.source['events'][self.index]
                if (e['kind'],e['rgb'],e['context'])!=(kind,rgb,context):raise ControlError('Native event/context mismatch at '+str(self.index)+': '+kind)
                if select:payload=copy.deepcopy(e['payload'])
                elif e['payload']!=payload:raise ControlError('Native result/control mismatch at '+str(self.index)+': '+kind)
            self._lifecycle(kind,rgb,payload)
            row={'type':'event','index':self.index,'kind':kind,'rgb':rgb,'context':context,
                 'payload':payload,'previous_sha256':self.previous}
            row['sha256']=digest(row);self._write(row);self.previous=row['sha256'];self.index+=1
            return payload
        except BaseException:
            self.failed=True;self.file.flush();raise

    def _lifecycle(self,kind,rgb,payload):
        if kind=='frame.begin':
            if self.open_frame is not None or self.open_operations or rgb!=self.last_frame+1 or payload.get('index')!=rgb-1:
                raise ControlError('Native frame lifecycle/order mismatch')
            self.open_frame=rgb
        elif kind=='frame.end':
            if self.open_frame!=rgb or self.open_operations or payload.get('next_input_index')!=rgb:
                raise ControlError('Unpaired native frame completion')
            self.open_frame=None;self.last_frame=rgb
        elif kind.endswith('.begin'):
            self.open_operations.append(kind[:-6])
        elif kind.endswith('.end'):
            if not self.open_operations or self.open_operations.pop()!=kind[:-4]:
                raise ControlError('Unpaired native nested operation')

    def seal(self,termination='PREFIX_RGB080'):
        if self.failed:raise ControlError('Failed native schedule cannot seal')
        if self.open_frame is not None or self.open_operations or self.last_frame!=80:
            raise ControlError('Native prefix cannot seal before complete RGB019..080')
        if self.mode=='replay' and self.index!=len(self.source['events']):raise ControlError('Replay has unconsumed events')
        self._write({'type':'footer','event_count':self.index,'last_sha256':self.previous,'termination':termination})
        self.file.close()

    def abort(self):
        self.failed=True
        if not self.file.closed:self.file.close()


def read_schedule(path):
    rows=[json.loads(x) for x in Path(path).read_text().splitlines()]
    if len(rows)<2 or rows[0].get('schema')!=SCHEMA or rows[-1].get('type')!='footer':raise ControlError('Unsealed native schedule')
    h=rows[0]['header'];prev=digest(h)
    if rows[0]['sha256']!=prev:raise ControlError('Native header SHA mismatch')
    frame=None;last_frame=18;operations=[]
    for i,e in enumerate(rows[1:-1]):
        if e.get('type')!='event' or e['index']!=i or e['previous_sha256']!=prev or e['sha256']!=digest({k:v for k,v in e.items() if k!='sha256'}):raise ControlError('Native event hash/order mismatch')
        if not 0<=e['rgb']<=80:raise ControlError('Schedule exceeds authorized prefix')
        kind,rgb,p=e['kind'],e['rgb'],e['payload']
        if kind=='frame.begin':
            if frame is not None or operations or rgb!=last_frame+1 or p.get('index')!=rgb-1:raise ControlError('Invalid saved frame order')
            frame=rgb
        elif kind=='frame.end':
            if frame!=rgb or operations or p.get('next_input_index')!=rgb:raise ControlError('Invalid saved frame completion')
            frame=None;last_frame=rgb
        elif kind.endswith('.begin'):operations.append(kind[:-6])
        elif kind.endswith('.end'):
            if not operations or operations.pop()!=kind[:-4]:raise ControlError('Invalid saved nested event order')
        prev=e['sha256']
    if rows[-1]!=dict(type='footer',event_count=len(rows)-2,last_sha256=prev,termination='PREFIX_RGB080'):
        raise ControlError('Native prefix termination mismatch')
    if h.get('init_D')!=0 or h.get('max_rgb')!=80 or h.get('W')!=1 or h.get('U')!=1:raise ControlError('Invalid native header scope')
    if frame is not None or operations or last_frame!=80:raise ControlError('Incomplete saved native prefix')
    return {'header':h,'events':rows[1:-1],'footer':rows[-1]}


class NativeControl(NullControl):
    enabled=True
    def __init__(self,D,output,*,journal=None,capture_callback=None,restore_values=None):
        if type(D) is not int or D not in (0,1):raise ControlError('Invalid native D')
        self.D=D;self.output=Path(output);self.journal=journal;self.capture_callback=capture_callback
        self.restore_values=restore_values;self.graphs={};self.graph_ids={};self.edge_state={};self.next_graph=0;self.next_edge=0
        self.nodes=[];self.rgb=0;self.phase='startup';self.init_counts={};self.initialized=False
        self.ba_calls=0;self.operation_stack=[];self.failed=False;self.expected_context=None
        self.trace=(self.output/'native_trace.jsonl').open('x',encoding='utf-8')
        self.stream=None;self.tracker=None;self.video=None;self.filler=None

    def diagnostic(self,kind,**fields):
        self.trace.write(json.dumps({'kind':kind,'rgb':self.rgb,'time_ns':time.time_ns(),**fields},sort_keys=True,allow_nan=False)+'\n');self.trace.flush()

    def _graph_rows(self,gid,graph,mutating):
        old=self.edge_state.get(gid,[]);used=set();rows=[]
        for state,an,bn in [('active','ii','jj'),('inactive','ii_inac','jj_inac'),('bad','ii_bad','jj_bad')]:
            a,b=getattr(graph,an,None),getattr(graph,bn,None)
            if a is None and b is None:continue
            if a is None or b is None or len(a)!=len(b):raise ControlError('Unpaired native graph indices')
            ages=getattr(graph,'age',None) if state=='active' else None
            for j,(i,k) in enumerate(zip(a.detach().cpu().tolist(),b.detach().cpu().tolist())):
                if not (0<=i<len(self.nodes) and 0<=k<len(self.nodes)):raise ControlError('Native graph refers to unknown stable RGB node')
                source,target=self.nodes[i],self.nodes[k]
                matches=[r for r in old if r['edge_id'] not in used and r['source']==source and r['target']==target]
                same=[r for r in matches if r['state']==state]
                prior=(same or matches)
                if prior:eid=prior[0]['edge_id'];used.add(eid)
                else:
                    if not mutating:raise ControlError('Graph topology changed without a recorded native operation')
                    eid='edge%08d'%self.next_edge;self.next_edge+=1
                rows.append({'edge_id':eid,'source':source,'target':target,'state':state,
                             'source_slot':i,'target_slot':k,'age':int(ages[j]) if ages is not None else None})
        if not mutating and rows!=old:raise ControlError('Graph state/age changed outside a recorded native operation')
        self.edge_state[gid]=rows
        return rows

    def context(self,mutating=False):
        graphs=[]
        for gid,g in self.graphs.items():graphs.append({'graph_id':gid,'edges':self._graph_rows(gid,g,mutating)})
        return {'slot_rgb_tokens':list(self.nodes),'graphs':graphs}

    def point(self,kind,payload,*,select=False,mutating=False):
        if self.failed:raise ControlError('Native controller stopped')
        try:
            ctx=self.context(mutating or bool(self.operation_stack))
            if self.journal:return self.journal.point(kind,self.rgb,ctx,payload,select=select)
            self.diagnostic(kind,payload=payload,context_sha256=digest(ctx));return payload
        except BaseException as e:
            self.failed=True;self.diagnostic('CONTROL_STOP',reason=str(e));raise

    def begin(self,kind,payload,select=True):
        selected=self.point(kind+'.begin',payload,select=select)
        self.operation_stack.append(kind)
        return selected

    def end(self,kind,payload):
        if not self.operation_stack or self.operation_stack[-1]!=kind:raise ControlError('Unpaired native operation: '+kind)
        self.point(kind+'.end',payload,mutating=True)
        self.operation_stack.pop()

    def graph_created(self,graph):
        gid='graph%04d'%self.next_graph;self.next_graph+=1
        self.graphs[gid]=graph;self.graph_ids[id(graph)]=gid;self.edge_state[gid]=[]
        self.point('graph.create',{'graph_id':gid,'corr_impl':graph.corr_impl,'max_factors':graph.max_factors})

    def gid(self,g):
        if id(g) not in self.graph_ids:raise ControlError('Unregistered native graph')
        return self.graph_ids[id(g)]

    def tracker_begin(self,tracker,stream,values):
        self.tracker,self.stream,self.video=tracker,stream,tracker.video
        if self.restore_values is not None:
            values=copy.deepcopy(self.restore_values);self.restore_values=None
        return values

    def frame_begin(self,index,timestamp):
        rgb=int(timestamp)+1
        if rgb!=index+1 or not 1<=rgb<=80:raise ControlError('Bounded native input order/RGB mismatch')
        self.rgb=rgb
        self.point('frame.begin',{'index':index,'rgb_id':rgb})

    def frame_end(self,tracker,stream,values):
        if tracker is not None:
            n=int(tracker.video.counter.value)
            stamps=tracker.video.timestamp[:n].detach().cpu().tolist()
            if n!=len(self.nodes) or any(v!=int(v) for v in stamps) or ['kf:%03d'%(int(v)+1) for v in stamps]!=self.nodes:
                raise ControlError('Native video counter/timestamps differ from the recorded stable RGB slot map')
        self.point('frame.end',{'next_input_index':values['next_input_index']})
        # A concrete C0 boundary needs both stages, all 24 calls and frame tail.
        if self.initialized and self.capture_callback:
            callback=self.capture_callback;self.capture_callback=None
            callback(tracker,stream,values,self)
            raise PrefixComplete('C0_CAPTURED_AFTER_TRUE_INITIALIZATION')
        if self.rgb==80:
            if self.journal:self.journal.seal()
            self.diagnostic('PREFIX_COMPLETE',last_rgb=80,formal_experiment=False)
            raise PrefixComplete('AUTHORIZED_RGB080_REACHED')

    def motion_decision(self,proposed,force,threshold,score=None):
        p=self.point('motion.decision',{'admitted':bool(proposed),'force':bool(force),'threshold':float(threshold),
                     'reason':None if proposed else 'BELOW_NATIVE_MOTION_THRESHOLD'},select=True)
        if set(p)!={'admitted','force','threshold','reason'} or type(p['admitted']) is not bool or type(p['force']) is not bool or p['threshold']!=float(threshold):
            raise ControlError('Invalid motion replay payload')
        self.diagnostic('motion.natural',admitted=bool(proposed),force=bool(force),score=score,scheduled_admitted=p['admitted'])
        return p['admitted'],p['force']

    def keyframe_decision(self,drop,**kw):
        p=self.point('keyframe.decision',{'drop':bool(drop),'reason':'NATIVE_LOCAL_DISTANCE' if drop else None},select=True)
        if type(p.get('drop')) is not bool:raise ControlError('Invalid keyframe replay decision')
        self.diagnostic('keyframe.natural',drop=bool(drop),scheduled_drop=p['drop'],**kw)
        return p['drop']

    def bad_edge_mask(self,graph,mask):
        import torch
        p=self.point('graph.bad_mask',{'graph_id':self.gid(graph),'mask':mask.detach().cpu().tolist()},select=True)
        if p['graph_id']!=self.gid(graph) or len(p['mask'])!=len(mask) or any(type(x) is not bool for x in p['mask']):raise ControlError('Invalid bad-edge mask')
        return torch.tensor(p['mask'],device=mask.device,dtype=torch.bool)

    def edge_plan(self,graph,es,loop_edges):
        natural=[[int(a),int(b)] for a,b in es]
        p=self.point('graph.backend_plan',{'graph_id':self.gid(graph),'edges':natural,'loop_edges':int(loop_edges)},select=True)
        if p['graph_id']!=self.gid(graph):raise ControlError('Backend graph identity mismatch')
        for a,b in p['edges']:
            if not 0<=a<len(self.nodes) or not 0<=b<len(self.nodes):raise ControlError('Impossible recorded backend edge')
        return p['edges'],p['loop_edges']

    def initialization_done(self,frontend):
        expected={'frontend_init_neighborhood':8,'frontend_init_proximity':8,'frontend_init_second':8}
        if self.init_counts!=expected or not frontend.is_initialized or frontend.t1!=frontend.warmup:
            raise ControlError('C0 initialization closure incomplete: '+repr(self.init_counts))
        self.initialized=True
        self.point('init.complete',{'graph_updates':24,'next_boundary':'TRACKER_FRAME_END','actual_rgb':self.rgb})

    def init_age_reset(self,graph):self.point('graph.init_age_reset',{'graph_id':self.gid(graph)},mutating=True)

    def depth_flag(self,phase,native):
        if phase in ('frontend_init_neighborhood','frontend_init_proximity','frontend_init_second'):return False
        if phase in ('frontend_local_predecision','frontend_local_retained'):return bool(self.D)
        return native

    def final_phase(self,kind,**payload):self.point('final.'+kind,payload)

    def filler_begin(self,video,n,m,t0,t1,timestamps):
        if m>16 or n+m>500:raise ControlError('Native Filler capacity exceeded')
        self.point('filler.batch.begin',{'n':n,'m':m,'rgb_ids':[int(t)+1 for t in timestamps],
                   'anchor_left':t0.cpu().tolist(),'anchor_right':t1.cpu().tolist()})
        self.nodes += ['filler:%d:%d'%(n,int(t)+1) for t in timestamps]

    def filler_end(self,n,m):
        self.point('filler.batch.result',{'n':n,'m':m},mutating=True)
        # Temporary graphs are retired before temporary nodes are invalidated.
        retire=[gid for gid,g in self.graphs.items() if gid!=self.gid(self.tracker.frontend.graph)]
        for gid in retire:
            self.graph_ids.pop(id(self.graphs[gid]),None);self.graphs.pop(gid);self.edge_state.pop(gid)
        del self.nodes[n:]
        self.point('filler.batch.end',{'counter_after':n},mutating=True)

    def export(self,rgb_ids,pose_sources):self.point('export',{'rgb_ids':rgb_ids,'pose_sources':pose_sources})

    def snapshot_discrete(self):
        if self.operation_stack:raise ControlError('Cannot capture inside an unfinished native operation')
        return {'nodes':list(self.nodes),'rgb':self.rgb,'initialized':self.initialized,'init_counts':dict(self.init_counts),
                'ba_calls':self.ba_calls,'next_graph':self.next_graph,'next_edge':self.next_edge,
                'edge_state':copy.deepcopy(self.edge_state),'graph_ids':{gid:graph for gid,graph in self.graphs.items()}}

    def restore_discrete(self,s):
        self.nodes=list(s['nodes']);self.rgb=s['rgb'];self.initialized=s['initialized'];self.init_counts=s['init_counts']
        self.ba_calls=s['ba_calls'];self.next_graph=s['next_graph'];self.next_edge=s['next_edge'];self.edge_state=s['edge_state']
        self.graphs=s['graph_ids'];self.graph_ids={id(g):gid for gid,g in self.graphs.items()}
        self.context()
