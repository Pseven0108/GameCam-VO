"""Discrete control schema: continuous optimization results never enter payloads."""
from control_common import ControlError,digest
# Payload fields are strict. Ordered RGB/slot/edge identity must come from runtime.
FIELDS={
 'frame_begin':('input_index','rgb_id','timestamp_token'),
 'motion_filter_decision':('admitted','force_flag','rejection_reason'),
 'candidate_insert':('keyframe_id','slot','generation','insertion_order'),
 'edge_add_request':('graph_id','source_indices','target_indices','remove'),
 'edge_insert':('graph_id','edges'),
 'edge_remove':('graph_id','edge_ids','store','reason'),
 'edge_age_advance':('graph_id','edge_ids','increment'),
 'ba_begin':('phase','call_id','t0','t1','outer_iteration','iterations','motion_only','use_inactive','enable_update_uncer','enable_udba'),
 'ba_end':('call_id',),
 'keyframe_decision':('retained','rejection_reason','force_flag'),
 'keyframe_remove':('keyframe_id','slot','slot_map_after'),
 'keyframe_commit':('keyframe_id','slot','insertion_order'),
 'initialization_phase':('phase','update_index','init_D','enable_udba','enable_update_uncer'),
 'frame_end':('next_input_index',),
 'final_ba_begin':('stage','steps','metric_depth_reg'),
 'final_graph_build':('graph_id','edges','nonempty'),
 'final_ba_end':('stage','metric_depth_reg_restored'),
 'filler_batch_begin':('batch_id','rgb_ids','slots','anchor_left','anchor_right'),
 'filler_graph_build':('graph_id','edges'),
 'filler_update':('call_id','iteration','t0','t1','iterations','motion_only'),
 'filler_batch_end':('batch_id','counter_after'),
 'export_complete':('pose_count','rgb_ids')}
BA_PHASES={'frontend_init_neighborhood','frontend_init_proximity','frontend_init_second','frontend_local_predecision','frontend_local_retained','final_global','filler'}

def validate_context(c):
    if set(c)!={'active_keyframe_ids','slot_map','ordered_edges'}:raise ControlError('Incomplete discrete context')
    ids=c['active_keyframe_ids'];slots=c['slot_map'];edges=c['ordered_edges']
    if len(set(ids))!=len(ids):raise ControlError('Duplicate keyframe identity')
    if any(set(s)!={'slot','keyframe_id','generation'} for s in slots):raise ControlError('Invalid slot identity')
    if len({s['slot'] for s in slots})!=len(slots) or any(type(s['slot']) is not int or s['slot']<0 for s in slots):raise ControlError('Invalid/duplicate slot')
    valid={s['slot'] for s in slots}
    eids=[]
    for e in edges:
        if set(e)!={'edge_id','graph_id','source','target','state'}:raise ControlError('Invalid edge identity')
        if e['source'] not in valid or e['target'] not in valid or e['state'] not in ('active','inactive','bad'):raise ControlError('Invalid graph endpoint/state')
        eids.append(e['edge_id'])
    if len(set(eids))!=len(eids):raise ControlError('Duplicate edge instance ID')
    return digest(c)

def validate_payload(kind,p):
    if kind not in FIELDS or set(p)!=set(FIELDS[kind]):raise ControlError('Unexpected/missing event fields: '+kind)
    # Discrete flags must not be coerced from arbitrary truthy values.
    for key in ('admitted','force_flag','retained','remove','store','motion_only','use_inactive','enable_update_uncer','enable_udba','nonempty','metric_depth_reg','metric_depth_reg_restored'):
        if key in p and type(p[key]) is not bool:raise ControlError('Expected boolean '+key)
    if 'rejection_reason' in p and not isinstance(p['rejection_reason'],(str,type(None))):raise ControlError('Bad rejection reason')
    if kind=='ba_begin':
        if p['phase'] not in BA_PHASES or any(type(p[k]) is not int or p[k]<0 for k in ('t0','t1','iterations','outer_iteration')) or p['t1']<p['t0']:raise ControlError('Invalid BA controls')
    if kind=='initialization_phase' and p['init_D']!=0:raise ControlError('Common initialization requires D=0')
    if kind=='filler_batch_begin' and not(len(p['rgb_ids'])==len(p['slots'])==len(p['anchor_left'])==len(p['anchor_right'])):raise ControlError('Inconsistent filler batch')
    return True


class EventLifecycle:
    """Semantic lifecycle in addition to JSONL byte integrity."""
    def __init__(self):
        self.frame=None;self.ba=None;self.final=None;self.filler=None;self.seen_calls=set();self.exported=False;self.count=0
    def accept(self,frame,kind,p):
        if type(frame) is not int or frame<0 or self.exported:raise ControlError('Invalid frame/event after export')
        if kind=='frame_begin':
            if self.frame is not None or self.ba is not None or self.filler is not None:raise ControlError('Nested input frame')
            self.frame=frame
        elif kind=='frame_end':
            if self.frame!=frame or self.ba is not None:raise ControlError('Unpaired input frame')
            self.frame=None
        elif kind=='ba_begin':
            if self.ba is not None or p['call_id'] in self.seen_calls:raise ControlError('Nested/duplicate BA call')
            self.ba=p['call_id'];self.seen_calls.add(self.ba)
        elif kind=='ba_end':
            if self.ba!=p['call_id']:raise ControlError('Unpaired BA completion')
            self.ba=None
        elif kind=='final_ba_begin':
            if self.frame is not None or self.ba is not None or self.final is not None:raise ControlError('Invalid final BA phase')
            self.final=p['stage']
        elif kind=='final_ba_end':
            if self.final!=p['stage'] or self.ba is not None:raise ControlError('Unpaired final BA')
            self.final=None
        elif kind=='filler_batch_begin':
            if self.frame is not None or self.ba is not None or self.final is not None or self.filler is not None:raise ControlError('Invalid filler phase')
            if len(p['rgb_ids'])>16 or any(type(x) is not int or x<0 or x>=500 for x in p['slots']):raise ControlError('Filler batch/capacity violation')
            self.filler=p['batch_id']
        elif kind=='filler_batch_end':
            if self.filler!=p['batch_id'] or self.ba is not None:raise ControlError('Unpaired filler batch')
            self.filler=None
        elif kind=='filler_update':
            if self.filler is None or p['call_id'] in self.seen_calls:raise ControlError('Filler update outside batch or duplicated call')
            self.seen_calls.add(p['call_id'])
        elif kind=='export_complete':
            if any(x is not None for x in (self.frame,self.ba,self.final,self.filler)) or p['pose_count']!=len(p['rgb_ids']):raise ControlError('Premature/incomplete export')
            self.exported=True
        self.count+=1
    def finish(self):
        if not self.exported or not self.count or any(x is not None for x in (self.frame,self.ba,self.final,self.filler)):raise ControlError('Incomplete schedule lifecycle')
