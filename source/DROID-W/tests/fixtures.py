import copy,torch
from checkpoint.state_schema import VIDEO,GRAPH,MOTION,FRONTEND
from checkpoint.rng_state import capture_rng_state
from control_common import digest

def state_fixture():
    cap=4;n=2
    v={k:torch.arange(cap*2,dtype=torch.float32).reshape(cap,2) for k in VIDEO}
    v['affine_weights']=torch.ones(3)
    g={k:torch.ones(2) for k in GRAPH}
    for suf in ('','_inac','_bad'):
        g['ii'+suf]=torch.tensor([0],dtype=torch.int64);g['jj'+suf]=torch.tensor([1],dtype=torch.int64)
    g['age']=torch.tensor([0],dtype=torch.int64);g['corr_pyramid']=[torch.ones(1,2,2)/(i+1) for i in range(4)]
    return {'video':v,'graph':g,'motion_filter':{k:torch.zeros(2) for k in MOTION},
        'frontend':{k:torch.zeros(2) for k in FRONTEND},'cursor':{'last_input_index':17,'next_input_index':18},'rng':capture_rng_state(),
        'runtime':{'capacity':cap,'counter':n,'first_mainloop_seen':False,'second_initialization_complete':True,'init_D':0,'keyframe_ids':[11,12]},
        'model_buffers':{'CPU_SYNTHETIC_BUFFER':torch.zeros(2)},'model_modes':{'CPU_SYNTHETIC_MODULE':False},'observer':{'ba_counter':24}}

def provenance():return {'artifact_kind':'CPU_SYNTHETIC_STATE','baseline_commit':'synthetic-no-baseline-run','fixture_version':1}
def header(schedule='S1'):
    return {'schema':'GAMECAM_SCHEDULE_V1','artifact_kind':'CPU_SYNTHETIC_SCHEDULE','schedule':schedule,'producer_D':1 if schedule=='S1' else 0,
        'init_D':0,'W':1,'U':1,'c0_sha256':digest({'synthetic':True}),'source_sha256':digest('synthetic-source'),'input_sha256':digest('no-rgb')}

def control_sequence():
    edge={'edge_id':'g:0:1','graph_id':'g','source':0,'target':2,'state':'active'}
    return [(18,'initialization_phase',{'phase':'frontend_init_second','update_index':23,'init_D':0,'enable_udba':True,'enable_update_uncer':True}),
      (19,'frame_begin',{'input_index':18,'rgb_id':19,'timestamp_token':'19'}),
      (19,'motion_filter_decision',{'admitted':True,'force_flag':False,'rejection_reason':None}),
      (19,'candidate_insert',{'keyframe_id':19,'slot':2,'generation':0,'insertion_order':2}),
      (19,'edge_add_request',{'graph_id':'g','source_indices':[0],'target_indices':[2],'remove':False}),
      (19,'edge_insert',{'graph_id':'g','edges':[edge]}),
      (19,'ba_begin',{'phase':'frontend_local_predecision','call_id':24,'t0':0,'t1':3,'outer_iteration':0,'iterations':2,'motion_only':False,'use_inactive':True,'enable_update_uncer':True,'enable_udba':True}),
      (19,'ba_end',{'call_id':24}),
      (19,'keyframe_decision',{'retained':True,'rejection_reason':None,'force_flag':False}),
      (19,'keyframe_commit',{'keyframe_id':19,'slot':2,'insertion_order':2}),
      (19,'edge_age_advance',{'graph_id':'g','edge_ids':['g:0:1'],'increment':1}),
      (19,'edge_remove',{'graph_id':'g','edge_ids':['g:0:1'],'store':False,'reason':'synthetic_age_cap'}),
      (19,'keyframe_remove',{'keyframe_id':19,'slot':2,'slot_map_after':[{'slot':0,'keyframe_id':11,'generation':0},{'slot':1,'keyframe_id':12,'generation':0}]}),
      (19,'frame_end',{'next_input_index':19}),
      (19,'final_ba_begin',{'stage':1,'steps':7,'metric_depth_reg':False}),
      (19,'final_graph_build',{'graph_id':'f','edges':[],'nonempty':False}),
      (19,'final_ba_end',{'stage':1,'metric_depth_reg_restored':True}),
      (19,'filler_batch_begin',{'batch_id':0,'rgb_ids':[19],'slots':[2],'anchor_left':[0],'anchor_right':[1]}),
      (19,'filler_graph_build',{'graph_id':'fill','edges':[]}),
      (19,'filler_update',{'call_id':25,'iteration':0,'t0':2,'t1':3,'iterations':2,'motion_only':True}),
      (19,'filler_batch_end',{'batch_id':0,'counter_after':2}),
      (19,'export_complete',{'pose_count':2,'rgb_ids':[11,12]})]
class ToyRuntime:
    """Discrete toy only. No geometry, native optimizer, dataset or model."""
    def __init__(self,D):
        self.D=D;self.continuous=0.0
        self.state={'active_keyframe_ids':[11,12],'slot_map':[{'slot':0,'keyframe_id':11,'generation':0},{'slot':1,'keyframe_id':12,'generation':0}],'ordered_edges':[]}
    def context(self):return copy.deepcopy(self.state)
    def apply(self,kind,p):
        s=self.state
        if kind=='candidate_insert':
            s['active_keyframe_ids'].append(p['keyframe_id']);s['slot_map'].append({k:p[k] for k in ('slot','keyframe_id','generation')})
        elif kind=='edge_insert':s['ordered_edges']+=copy.deepcopy(p['edges'])
        elif kind=='edge_remove':s['ordered_edges']=[e for e in s['ordered_edges'] if e['edge_id'] not in p['edge_ids']]
        elif kind=='keyframe_remove':
            s['active_keyframe_ids'].remove(p['keyframe_id']);s['slot_map']=copy.deepcopy(p['slot_map_after'])
        elif kind in ('final_graph_build','filler_graph_build'):s['ordered_edges']+=copy.deepcopy(p['edges'])
        if kind in ('ba_begin','filler_update'):self.continuous+=(1+self.D)*0.123

def events_fixture(D=1):
    toy=ToyRuntime(D);out=[]
    for frame,kind,p in control_sequence():
        before=toy.context();toy.apply(kind,p);out.append((frame,kind,p,before,toy.context()))
    return out,toy
