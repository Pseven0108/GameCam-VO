"""Freeze representative state rules using existing event metadata, not new scores."""
import os,sys,pathlib,json,csv,hashlib,shutil,datetime
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];OLD=ROOT.parent/'DROID_W_TASK004C_B_IO_COMPAT_20261124_R1'
A=ROOT.parent/'GAMECAM_TASK005A_D_SCHEDULE_MECHANISM_20261125_R1'
RECEIVER=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125')
def write(name,obj):
    (ROOT/'01_protocol'/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()
with (A/'03_evaluation/TASK005A_BA_MECHANISM_TIMELINE.csv').open(encoding='utf-8-sig') as f:allrows=list(csv.DictReader(f))
byarm={a:[r for r in allrows if r['arm']==a and r['stage']=='frontend_local_predecision'] for a in ('B1','B2','B4','B3')}
common=set.intersection(*({int(r['rgb']) for r in rows} for rows in byarm.values()))
windows={'early':(19,19,19),'near_reversal':(229,237,233),'late':(393,409,401)}
selected=[]
for phase,(lo,hi,center) in windows.items():
    eligible=sorted((r for r in common if lo<=r<=hi),key=lambda r:(abs(r-center),r))
    if not eligible:raise RuntimeError('No common event in predefined window: '+phase)
    rgb=eligible[0]
    for arm in ('B1','B2','B4','B3'):
        row=min((r for r in byarm[arm] if int(r['rgb'])==rgb),key=lambda r:int(r['ba_id']))
        selected.append({k:row[k] for k in ('arm','D','schedule','ba_id','rgb','stage','active_KF','pose_window','edge_count')}|{'selection_phase':phase,'historical_full_BA_input_available':False,'new_capture_required':True})
with (ROOT/'01_protocol/STATE_SELECTION.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(selected[0]));w.writeheader();w.writerows(selected)
c0=json.loads((ROOT/'00_intake/C0_MANIFEST_INTAKE.json').read_text())
provenance=c0['provenance'];remote=json.loads((ROOT/'00_intake/REMOTE_READONLY.stdout.json').read_text())
source_root=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE')
inventory={}
for arm in ('B1','B2','B4','B3'):
    p=OLD/'raw_evidence/R3_OFFLINE/attempts'/arm
    if not p.exists():p=RECEIVER/'raw_evidence/R3_OFFLINE/attempts'/arm
    inventory[arm]={'observer_sha256':sha(p/'observer.jsonl'),'native_trace_sha256':sha(p/'native_trace.jsonl'),'schedule_sha256':sha(p/'schedule.jsonl'),'full_state_files_at_target_BA':[]}
write('HISTORICAL_STATE_AVAILABILITY.json',{'C0_boundary':provenance['actual_boundary_rgb'],'C0_state_digest':c0['state_sha256'],'C0_archive_bytes':(RECEIVER/'C0_IMMUTABLE_LOCAL_BACKUP.tar').stat().st_size,'C0_uncompressed_storage_bytes':provenance['inventory']['storage_bytes'],'C0_not_equal_RGB019_BA_input':True,'historical_target_BA_states_available':0,'target_contexts':len(selected),'full_input_cannot_be_recovered_from_summary_statistics':True,'arms':inventory,'no_checkpoint_deserialization':True})
write('RESOURCE_STATUS.json',{'user_confirmed_GPU_mode':'NO_GPU_BOOT','remote_connection_authenticated':True,'gpu_native_run_allowed_by_current_resources':False,'disk_free_bytes_at_probe':remote['disk']['free'],'disk_GiB':remote['disk']['free']/1024**3,'shm_bytes':remote['shm']['total'],'reserve_bytes':10*1024**3,'headroom_above_reserve_bytes':remote['disk']['free']-10*1024**3,'local_C_free_bytes':shutil.disk_usage(RECEIVER).free,'local_D_free_bytes':shutil.disk_usage(ROOT).free,'exact_new_capture_size':'UNKNOWN_UNTIL_LIVE_INPUT_STORAGE_INVENTORY','gpu_run_seconds':'UNKNOWN','no_disk_cleanup_performed':True})
write('TASK005B_EXECUTION_PROTOCOL.json',{'schema':'TASK005B_DEPTH_PATH_V1','status':'PREPARED_NOT_GPU_EXECUTED','baseline':'c3414af6047d06bafc1a6645d09f23247f3b2cdc','sealed_Task004CB_modified':False,'cells':{'A':[1,1],'B':[1,0],'C':[0,1],'D':[0,0]},'curvature_regularizer':'c*m*alpha + (1-c*m)*eta','depth_rhs':'w_geometry - g*m*alpha*(disp-mono)','m':'mono > 0, computed from unchanged cached real mono prior even for D0-origin state','U_modes':['FROZEN','NATIVE_UPDATE'],'W_enabled':True,'native_inner_iterations_per_call':2,'state_selection':selected,'maximum_new_prefix_passes':4,'maximum_RGB_per_prefix':max(int(r['rgb']) for r in selected),'prefix_start_RGB':19,'new_prefix_inputs_total_max':4*(max(int(r['rgb']) for r in selected)-18),'final_BA_in_capture':False,'filler_in_capture':False,'new_full487_run':False,'original_states_may_not_be_bitwise_recoverable':True,'first_iteration_is_direct_effect':True,'second_iteration_is_conditional_U_feedback':True,'replay_cells_per_state':8,'native_endpoint_control_calls_per_state':4,'maximum_state_contexts':12,'maximum_native_calls':144,'possible_deduplication':'ONLY exact full input tensor+scalar+storage-relationship identity; not six historic hashes','freeze_graph_and_all_continuous_inputs_per_state':True,'statistical_unit':'captured state; exploratory case study, not independent BA events','no_automatic_retry':True,'no_TASK005C_or_TASK006':True})
print(json.dumps({'selected_RGB':sorted({int(r['rgb']) for r in selected}),'contexts':len(selected),'existing_complete_target_BA_states':0,'native_replays_executed':0}))
if __name__=='__main__':pass
