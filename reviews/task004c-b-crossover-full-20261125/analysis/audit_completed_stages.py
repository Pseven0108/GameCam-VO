"""Replay/control/receipt audit, CPU-only; never initiates any model execution."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import collections,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'source_reference'))
from native_control.runtime import read_schedule
DATA=ROOT/'raw_evidence/R2_READY/attempts';OUT=ROOT/'evaluation';OUT.mkdir(exist_ok=True)
SPEC={'restore_check':(19,0,None),'record_S1':(80,1,'S1'),'replay_D0_S1':(80,0,'S1'),'record_S0':(80,0,'S0'),'replay_D1_S0':(80,1,'S0'),'B1':(487,1,'S1'),'B2':(487,0,'S1'),'B4':(487,0,'S0'),'B3':(487,1,'S0')}
reports=[]
for mode,(end,D,schedule) in SPEC.items():
 p=DATA/mode
 if not (p/'PROCESS_RECEIPT.json').exists():continue
 receipt=json.loads((p/'PROCESS_RECEIPT.json').read_text());s=json.loads((p/'SUCCESS.json').read_text())
 assert receipt['exit_code']==0 and s['last_rgb']==end
 restore=json.loads((p/'RESTORE_RECEIPT.json').read_text());assert restore['all_tensor_and_object_nodes_match'] and restore['next_input_match'] and restore['rng_restored_last'] and restore['source_pid']!=restore['new_process_pid']
 trace=[json.loads(x) for x in (p/'native_trace.jsonl').read_text().splitlines()]
 journal=read_schedule(p/'schedule.jsonl') if schedule else None
 events=journal['events'] if journal else trace
 begin=[x['rgb'] for x in events if x['kind']=='frame.begin'];ends=[x['rgb'] for x in events if x['kind']=='frame.end']
 assert begin==ends==list(range(19,end+1)),mode
 obs=[json.loads(x) for x in (p/'observer.jsonl').read_text().splitlines()]
 bas=collections.defaultdict(dict)
 for row in obs:
  if row['type'] in ('ba_before','ba_after_native','ba_after_clamp'):bas[row['ba_id']][row['type']]=row
 before=[x['ba_before'] for x in bas.values()]
 for b in bas.values():assert set(b)=={'ba_before','ba_after_native','ba_after_clamp'},(mode,b.keys())
 local=[x for x in before if x['stage'] in ('frontend_local_predecision','frontend_local_retained') and not x['motion_only']]
 for x in local:assert x['metric_depth_prior_selected']==bool(D) and x['source_uba'] is True and x['update_u'] is True,(mode,x['ba_id'])
 if schedule:journal=read_schedule(p/'schedule.jsonl');assert journal['header']['consumer_D']==D and journal['header']['schedule']==schedule and journal['header']['c0_sha256']==s['c0_sha256']
 reports.append({'mode':mode,'status':'PASS','real_tracker_frame_events':len(begin),'first_rgb':begin[0],'last_rgb':end,'object_nodes_match':restore['object_nodes'],'full_BA_triplets':len(bas),'local_BA_D_W_U_calls_verified':len(local),'schedule_events':len(journal['events']) if schedule else None,'rerun_bytes':(p/'rerun_stream.rrd').stat().st_size,'formal':end==487})
pairs=[]
for a,b in (('record_S1','replay_D0_S1'),('record_S0','replay_D1_S0'),('B1','B2'),('B4','B3')):
 if not (DATA/a/'SUCCESS.json').exists() or not (DATA/b/'SUCCESS.json').exists():continue
 x=read_schedule(DATA/a/'schedule.jsonl');y=read_schedule(DATA/b/'schedule.jsonl');assert len(x['events'])==len(y['events'])
 for u,v in zip(x['events'],y['events']):
  for key in ('index','kind','rgb','context','payload'):assert u[key]==v[key],(a,b,u['index'],key)
 tx=[json.loads(z) for z in (DATA/a/'native_trace.jsonl').read_text().splitlines()];ty=[json.loads(z) for z in (DATA/b/'native_trace.jsonl').read_text().splitlines()]
 cx=[q for q in tx if q['kind']=='ba.continuous.after'];cy=[q for q in ty if q['kind']=='ba.continuous.after'];assert len(cx)==len(cy)
 dif=sum(u['tensor_sha256']['poses']!=v['tensor_sha256']['poses'] for u,v in zip(cx,cy));assert dif>0
 pairs.append({'producer':a,'consumer':b,'identical_discrete_events':len(x['events']),'same_topology_and_BA_schedule':True,'BA_pose_updates_differ':dif,'independent_continuous_states':True})
report={'stages_verified':len(reports),'stages':reports,'pairs':pairs,'formal_complete':sum(x['formal'] for x in reports),'missing':[m for m in SPEC if not (DATA/m/'SUCCESS.json').exists()]}
(OUT/'COMPLETED_STAGE_CONTROL_AUDIT.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
