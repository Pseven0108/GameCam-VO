import pathlib,json,csv,hashlib,shutil,difflib,os
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1];PARENT=ROOT.parent
OUT=ROOT/'reports';OUT.mkdir(exist_ok=True)
def read(p):return json.loads((ROOT/p).read_text(encoding='utf8'))
def csvread(p):
 with (ROOT/p).open(newline='',encoding='utf8') as f:return list(csv.DictReader(f))
def csvwrite(name,rows):
 with (ROOT/'results'/name).open('w',newline='',encoding='utf8') as f:
  fields=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
endpoints=csvread('results/TASK004C_FIXED_STATE_ENDPOINT_METRICS.csv');common=csvread('results/COMMON_SUPPORT_RESIDUALS.csv');Arows=[];res=[];pos=[]
for a in ['E0','E1']:
 ck=read(f'native_small/{a}/CHECKPOINT.json');cap=read(f'captures/{a}/CAPTURE_COMPLETE.json');prior=read(f'results/{a}_PRIOR_VS_GEOMETRY.json')
 for D in [1,0]:
  endpoint=next(r for r in endpoints if r['arm']==a and r['D']==str(D));r=read(f'native_small/{a}_D{D}/REPLAY_COMPLETE.json');restore=read(f'native_small/{a}_D{D}/INPUT_RESTORATION.json');c=next(r for r in common if r['state']==a and r['D']==str(D));diag=read(f'results/{a}_D{D}_NUMERIC_DIAGNOSTICS.json')
  Arows.append(dict(**endpoint,checkpoint_sha256=restore['checkpoint_file_sha256'],common_input_digest=restore['common_input_digest'],input_hashes_exact=restore['all_hashes_exact'],W=1,U=1,native_calls=1,inner_iterations=2,observer_ba_id=ck['observer_ba_id'],active_keyframes=ck['active_count'],graph_edges=ck['arrays']['ii']['shape'][0],negative_native_active=r['negative_disparities_native_active'],clamp_affected_active=r['clamp_affected_active'],native_ba_seconds=r['native_seconds'],status='COMPLETE',same_D_repeat_count=1,full487_experiment=False,filler=False))
  res.append(dict(arm=a,D=D,classification='CPU_RECONSTRUCTED_PARTIAL_TERMS',common_support_pixels=c['common_valid_pixels'],common_geometry_sse_fixed_initial_U=c['common_support_sse_frozen_initial_U'],common_geometry_sse_updated_U=c['common_support_sse_current_U'],common_reprojection_rms_lowres_px=c['common_support_rms_lowres_px'],individual_support_geometry_sse=diag['geometry_after_native_fixed_initial_U']['weighted_geometry_sse'],mono_sse_before=diag['mono_residual_sse_before'],mono_sse_after=diag['mono_residual_sse_after_native'],gamma_depth=ck['scalars']['gamma_depth'],U_active_median=c['U_active_median'],U_active_p90=c['U_active_p90'],U_active_p95=c['U_active_p95'],effective_uba_mean_initial=c['effective_uba_mean_initial'],effective_uba_mean_current=c['effective_uba_mean_current'],disparity_update_l2=diag['disparity_delta']['l2'],U_update_l2=diag['U_delta']['l2'],full_native_objective='UNAVAILABLE',full_joint_Hessian='UNAVAILABLE',Schur_condition_number='UNAVAILABLE'))
  pr=[r for r in csvread('results/TASK004C_PER_POSE_UPDATES.csv') if r['arm']==a and r['D']==str(D) and r['inside_pose_window']=='True']
  pos.append(dict(arm=a,D=D,optimized_poses=len(pr),camera_center_update_mean_raw=float(np.mean([float(r['camera_center_update_raw']) for r in pr])),camera_center_update_max_raw=max(float(r['camera_center_update_raw']) for r in pr),rotation_update_mean_deg=float(np.mean([float(r['rotation_update_deg']) for r in pr])),rotation_update_max_deg=max(float(r['rotation_update_deg']) for r in pr),returned_dx_scope='LAST_INNER_ITERATION_ONLY',returned_dx_l2=diag['native_return_last_inner_dx']['l2'],returned_dz_l2=diag['native_return_last_inner_dz']['l2']))
csvwrite('TASK004C_A_FIXED_STATE_D_TOGGLE.csv',Arows);csvwrite('TASK004C_A_BA_RESIDUAL_ANALYSIS.csv',res);csvwrite('TASK004C_A_POSE_UPDATE_COMPARISON.csv',pos)
for f in ['TASK004C_B_KEYFRAME_SCHEDULE_MANIFEST.csv','TASK004C_B_HISTORICAL_BA_BOUNDARY_GRAPH.csv']:
 q=PARENT/'results'/f
 if q.exists():shutil.copy2(q,ROOT/'results'/f)
blocked=[]
for arm,D,S in [('B1',1,'S1'),('B2',0,'S1'),('B3',1,'S0'),('B4',0,'S0')]:blocked.append(dict(arm=arm,D=D,schedule=S,status='NOT_EXECUTED_BLOCKED',common_full_initial_state=False,executable_mutation_schedule=False,new_GPU_runs=0,Sim3_ATE='',SE3_ATE='',reason='No complete common RGB18 frontend restart checkpoint; no executable cache/graph mutation schedule; RGB328 A states are divergent.'))
csvwrite('TASK004C_B_CROSSOVER_RESULTS.csv',blocked)
csvwrite('TASK004C_B_GRAPH_TOPOLOGY_COMPARISON.csv',[dict(arm=r['arm'],status=r['status'],schedule=r['schedule'],forced_graph_verified=False,actual_edges='',comparison='UNAVAILABLE_NO_B_RUN',historical_boundary_graph='TASK004C_B_HISTORICAL_BA_BOUNDARY_GRAPH.csv') for r in blocked])
csvwrite('TASK004C_B_DIRECT_ENDPOINT_COMPARISON.csv',[dict(arm=r['arm'],endpoint=ep,status='UNAVAILABLE_NOT_EXECUTED',direct_keyframe_pose='',Filler_pose='',displacement_ratio_pct='',translation_rpe='',rotation_rpe='') for r in blocked for ep in ['312-328','309-325','301-353']])
(ROOT/'results/REVIEW_SUMMARY_DATA.json').write_text(json.dumps({'A':Arows,'residuals':res,'pose_updates':pos,'B':blocked},indent=2))
diffdir=ROOT/'source_diffs';diffdir.mkdir(exist_ok=True)
for old,new in [('source/task004_run_segment.py','tools/task004c_prefix.py'),('source/task004_controls.py','tools/task004_controls.py')]:
 a=(ROOT/old).read_text(encoding='utf8').splitlines(keepends=True);b=(ROOT/new).read_text(encoding='utf8').splitlines(keepends=True);(diffdir/(pathlib.Path(new).stem+'.diff')).write_text(''.join(difflib.unified_diff(a,b,fromfile=old,tofile=new)),encoding='utf8')
for name in ['checkpoint_io.py','task004c_capture.py','replay_one.py','remote_operation.py']:
 text=(ROOT/'tools'/name).read_text(encoding='utf8').splitlines(keepends=True);(diffdir/(name+'.diff')).write_text(''.join(difflib.unified_diff([],text,fromfile='/dev/null',tofile='isolated/'+name)),encoding='utf8')
sec=dict(task='TASK004C_APPROVED_PREFIX_RECOVERY_AND_REPLAY',prefix_captures=2,each_prefix_frames=328,native_ba_replay_processes=4,native_ba_calls_per_replay=1,native_inner_iterations_per_replay=2,other_native_BA_during_prefix='Original frontend calls before capture; see observer logs',full487_new_runs=0,automatic_retries=0,experiment_B_runs=0,gpu_used=True,cuda_initialized=True,pretrained_models_loaded_in_prefix=True,model_forward_in_prefix=True,model_loaded_in_BA_only_replays=False,GT_used_in_model_input=False,GT_used_offline=True,Final_BA_executed=False,Filler_executed=False,original_R2_YAML_modified=False,frozen_source_modified=False,weights_modified=False,extension_recompiled=False,historical_results_modified=False,shutdown=False,reboot=False,GPU_allocation_kept_online=True,browser_visualization='USER_DEFERRED_NOT_VERIFIED',RRD_recordings='PRESERVED_TWO_UNIQUE_CAPTURES',B_status='BLOCKED_COMMON_STATE_AND_EXECUTABLE_SCHEDULE')
(ROOT/'SECURITY_AUDIT.json').write_text(json.dumps(sec,indent=2),encoding='utf8')
log=['# 执行记录','','所有运行在独立Task004C recovery目录；保留失败的准备日志。']
for label,p in [('Capture E0','captures/E0/STATUS.json'),('Capture E1','captures/E1/STATUS.json')]+[(f'Replay {a}',f'native_small/{a}/STATUS.json') for a in ['E0_D1','E0_D0','E1_D1','E1_D0']]:
 s=read(p);log.append(f"- {label}: phase={s['phase']}; exit={s['exit_code']}; elapsed={s['elapsed']:.6f}s; peak GPU={s['peak_gpu_mib']}MiB; peak shm={s['peak_shm_bytes']}B.")
log+=['- 初始默认Python缺少NumPy，改用现有CPU依赖；无安装。','- 准备阶段UTF-8授权读取问题在模型启动前修正；原错误日志保留。这不是GPU重试。','- 合同测试10/10，独立分析测试14/14；输出和退出码见test_logs。','- 两次远端CPU分析退出码均0；本地端点评价退出码0。','- 无CUDA/native运行失败，无自动GPU重试。','- 原始源码208项与其他保护文件复核通过；GPU查询0MiB计算占用，实例保持在线。','- 原始快照归档与下载由独立收据记录，此处不伪造完成。']
(ROOT/'EXECUTION_LOG.md').write_text(chr(10).join(log)+chr(10),encoding='utf8')
print(json.dumps(dict(A_rows=len(Arows),B_rows=len(blocked),status='A_COMPLETE_B_BLOCKED',plot='EXISTING_REMOTE_CPU_ENVIRONMENT')))
