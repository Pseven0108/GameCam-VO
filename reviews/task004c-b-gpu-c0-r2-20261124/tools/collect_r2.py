"""Collect failed C0 closure evidence without changing source or restarting a model."""
import base64,io,json,zipfile
from remote_cpu import ROOT,call
code=r'''
import ast,base64,collections,hashlib,io,json,pathlib,shutil,stat,subprocess,zipfile
root=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_GPU_C0_R2_20261124_R1');src=root/'source_candidate';out=root/'attempts/capture'
receipt=json.loads((out/'PROCESS_RECEIPT.json').read_text());assert receipt['exit_code']==1
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
trace=[json.loads(line) for line in (out/'native_trace.jsonl').read_text().splitlines() if line.strip()]
kind_counts=dict(collections.Counter(r['kind'] for r in trace))
updates=[r for r in trace if r['kind']=='graph.update.end'];phase_counts=dict(collections.Counter(r['payload']['phase'] for r in updates))
ba_begin=[r for r in trace if r['kind']=='native.ba.begin'];ba_end=[r for r in trace if r['kind']=='native.ba.end']
frames=[r for r in trace if r['kind']=='frame.end'];init=[r for r in trace if r['kind']=='init.complete']
assert phase_counts=={'frontend_init_neighborhood':8,'frontend_init_proximity':8,'frontend_init_second':8}
assert len(ba_begin)==len(ba_end)==24 and len(frames)==18 and len(init)==1
assert init[0]['rgb']==18 and frames[-1]['payload']['next_input_index']==18
assert not (root/'C0').exists()
stderr=(out/'process.stderr.txt').read_text();assert 'LoRALinear.lora_dropout: Unregistered closure/function' in stderr
module=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/torch_hub/yvanyin_metric3d_main/mono/model/decode_heads/RAFTDepthNormalDPTDecoder5.py')
text=module.read_text();tree=ast.parse(text)
classes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='LoRALinear'];assert len(classes)==1
cls=classes[0];lines=text.splitlines();excerpt='\n'.join('%d: %s'%(i+1,lines[i]) for i in range(cls.lineno-1,cls.end_lineno))
(root/'evidence/Metric3D_LoRALinear_source.txt').write_text(excerpt)
lambdas=[]
for node in ast.walk(cls):
 if isinstance(node,ast.Lambda):
  args=[a.arg for a in node.args.args];identity=len(args)==1 and isinstance(node.body,ast.Name) and node.body.id==args[0]
  lambdas.append({'line':node.lineno,'AST':ast.dump(node,include_attributes=False),'single_argument_identity':identity})
callable_evidence={'source_path':str(module),'source_sha256':sha(module),'class_line':cls.lineno,
 'class_end_line':cls.end_lineno,'lambdas':lambdas,
 'actual_runtime_failure_path':'Tracker.motion_filter.metric_depth_estimator...LoRALinear.lora_dropout',
 'actual_object_not_recovered_after_exit':True,'identity_lambda_identification_is_source_based':True,
 'model_or_serializer_patched':False,'additional_unsupported_fields_unknown':True}
(root/'artifacts/CLOSURE_BLOCKER_EVIDENCE.json').write_text(json.dumps(callable_evidence,indent=2))
backings=[]
for path in sorted((out/'shared_cpu').glob('*.bin')):
 s=path.stat();backings.append({'path':str(path),'bytes':s.st_size,'allocated_bytes':s.st_blocks*512,
  'st_dev':s.st_dev,'inode':s.st_ino,'mode':stat.S_IMODE(s.st_mode),'sha256':sha(path),'retained':True})
pgid=json.loads((out/'PROCESS_STARTED.json').read_text())['pgid'];maps=[];errors=[];pgroup=[]
for proc in pathlib.Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:
  maptext=(proc/'maps').read_text()
  if str(out/'shared_cpu')+'/' in maptext:maps.append(int(proc.name))
  raw=(proc/'stat').read_text();fields=raw[raw.rfind(')')+2:].split()
  if int(fields[2])==pgid:pgroup.append(int(proc.name))
 except (FileNotFoundError,ProcessLookupError):pass
 except PermissionError:errors.append(int(proc.name))
gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=15)
samples=[json.loads(line) for line in (out/'resource_samples.jsonl').read_text().splitlines() if line.strip()]
peaks=[int(x['GPU'].split(',')[0]) for x in samples if x.get('GPU_query_exit')==0 and x.get('GPU')]
rrd=[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in out.rglob('*.rrd')]
lock=json.loads((root/'configs/identity_lock.json').read_text());pins={}
for path,expected in {**lock['remote_pins'],**lock['execution_source_pins']}.items():
 actual=sha(path);assert actual==expected;pins[path]={'expected':expected,'actual':actual,'match':True}
head=subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()
changed=subprocess.check_output(['git','-C',str(src),'diff','668a88c74c7f7a88a572679d2bd8e86c0a05514b','--name-only'],text=True).splitlines()
assert changed==['native_control/dataset.py']
assert not subprocess.check_output(['git','-C',str(src),'status','--porcelain','--untracked-files=no'])
for name in ['native_control/dataset.py','native_control/snapshot.py','native_control/binding.py','src/tracker.py']:
 dest=root/'evidence/source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src/name,dest)
summary={'status':'BLOCKED_AT_C0_CLOSURE_UNREGISTERED_LORA_DROPOUT_FUNCTION','source_commit':head,
 'runtime_parent_commit':'668a88c74c7f7a88a572679d2bd8e86c0a05514b','changed_runtime_files':changed,
 'GPU_native_lifecycles':1,'GPU_exit_code':receipt['exit_code'],'runtime_seconds':receipt['runtime_seconds'],
 'real_frames_completed':18,'last_completed_RGB':18,'next_input_index':18,'next_RGB_id':19,
 'graph_update_phase_counts':phase_counts,'first_stage_graph_updates':16,'second_stage_graph_updates':8,
 'native_BA_calls_begun':len(ba_begin),'native_BA_calls_completed':len(ba_end),
 'requested_native_inner_iterations':sum(r['payload']['controls']['iters'] for r in ba_begin),
 'initialization_complete':True,'C0_save_callback_reached':True,'frame_end_before_next_input_verified':True,
 'C0_created':False,'complete_C0_bytes':None,'exact_complete_C0_budget_computed':False,
 'snapshot_failure_stage':'state_inventory/ObjectEncoder before prepare_state or any C0 payload write',
 '47_families_C0_persisted':0,'RNG_persisted':False,'model_buffers_C0_persisted':False,
 'Restore_executed':False,'S0_S1_created':False,'cross_D_executed':False,'B1_B2_B3_B4_executed':False,
 'GPU_retried':False,'sampled_GPU_peak_used_MiB':max(peaks),'sampled_shm_peak_bytes':max(x['shm_used'] for x in samples),
 'trace_kind_counts':kind_counts,'init_event':init[0],'last_frame_end_event':frames[-1],
 'closure_blocker':callable_evidence,'backing_files':backings,'backing_files_retained_for_failure_evidence':True,
 'remaining_attempt_pgroup':pgroup,'active_Arena_maps':maps,'proc_maps_permission_errors':errors,
 'GPU_compute_apps_after':{'exit_code':gpu.returncode,'stdout':gpu.stdout,'stderr':gpu.stderr},
 'rerun_recordings':rrd,'Rerun_browser_rendering_verified':False,
 'disk_after':dict(zip(('total','used','free'),shutil.disk_usage(root))),
 'shm_after':dict(zip(('total','used','free'),shutil.disk_usage('/dev/shm'))),
 'protected_pins_after':pins,'algorithm_formula_modified':False,'historical_files_deleted':0,'server_shutdown':False}
(root/'artifacts/GPU_C0_R2_POSTMORTEM.json').write_text(json.dumps(summary,indent=2))
protocol=json.loads((root/'evidence/APPROVED_47_FAMILY_PROTOCOL.json').read_text())
state={'schema':'GAMECAM_C0_R2_CAPTURE_STATUS_V1','complete':False,'C0_exists':False,'complete_C0_bytes':None,
 'failure':summary['status'],'source_commit':head,'actual_boundary_verified':True,'families':[],
 'RNG':'NOT_PERSISTED','model_buffers':'NOT_PERSISTED','aliases':'NO_COMPLETE_PERSISTED_STATE_TO_VERIFY',
 'Restore':'NOT_EXECUTED'}
for family in protocol['tensors']:
 row=dict(family);row['capture_status']='NOT_PERSISTED_IN_C0';row['verification']='NO_COMPLETE_C0';state['families'].append(row)
assert len(state['families'])==47
(root/'artifacts/TASK004C_B_C0_STATE_MANIFEST.json').write_text(json.dumps(state,indent=2))
memory=io.BytesIO();selected=[]
for directory in [root/'evidence',root/'artifacts',root/'cpu_tests',root/'operational',out]:
 for p in directory.rglob('*'):
  if p.is_file() and p.suffix in ('.py','.patch','.txt','.json','.jsonl') and p.name!='LAUNCH_INTENT.json' and p.stat().st_size<12*1024**2:selected.append(p)
selected.append(root/'RUN_AUTHORIZATION.json')
with zipfile.ZipFile(memory,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(set(selected)):z.write(p,p.relative_to(root).as_posix())
print(json.dumps({'summary':summary,'artifacts_b64':base64.b64encode(memory.getvalue()).decode()}))
'''
d=json.loads(call('COLLECT_C0_R2_CLOSURE_FAILURE',code,timeout=180));raw=base64.b64decode(d.pop('artifacts_b64'))
with zipfile.ZipFile(io.BytesIO(raw)) as z:
 assert z.testzip() is None
 target=ROOT/'remote_evidence';target.mkdir(exist_ok=False);z.extractall(target)
(ROOT/'evidence/GPU_C0_R2_POSTMORTEM.json').write_text(json.dumps(d['summary'],indent=2))
print(json.dumps({k:v for k,v in d['summary'].items() if k not in ('closure_blocker','protected_pins_after','backing_files','trace_kind_counts','init_event','last_frame_end_event')}))
print(json.dumps({'closure_source':d['summary']['closure_blocker']}))
