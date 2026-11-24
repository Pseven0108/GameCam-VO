import pathlib,sys,json,csv,subprocess,time,hashlib,zipfile,shutil,math
from datetime import datetime,timezone
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'evaluation';REPORT=ROOT/'reports';REPORT.mkdir(exist_ok=True)
CPU=r'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1119-907-0_26.1119.907.0_x64__3k8sg7r9htsxt/dependencies/python/python.exe'
utc=lambda:datetime.now(timezone.utc).isoformat()
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def put(p,d):
 with p.open('x',encoding='utf-8') as f:json.dump(d,f,indent=2,ensure_ascii=False,allow_nan=False)
def text(n,t):
 with (REPORT/n).open('x',encoding='utf-8') as f:f.write(t)
start=time.monotonic()
while not (ROOT/'evidence/ALL_LOCAL_ARCHIVES_VERIFIED.json').exists():
 if (ROOT/'evidence/DATA_PRIORITY_RESUME_FAILURE.json').exists():raise RuntimeError('campaign failure')
 assert time.monotonic()-start<7200,'result retrieval timeout'
 time.sleep(10)
print('STARTING_CPU_OFFLINE_EVALUATION',flush=True)
args=[CPU,'-X','utf8',str(ROOT/'tools/offline_analyze.py')]
with (ROOT/'evidence/offline_analysis.stdout.txt').open('xb') as out,(ROOT/'evidence/offline_analysis.stderr.txt').open('xb') as err:
 p=subprocess.run(args,cwd=ROOT,stdout=out,stderr=err,timeout=1200)
put(ROOT/'evidence/OFFLINE_ANALYSIS_PROCESS_RECEIPT.json',dict(argv=args,exit_code=p.returncode,utc=utc(),cpu_only=True))
assert p.returncode==0,(ROOT/'evidence/offline_analysis.stderr.txt').read_text(errors='replace')[-2500:]
summ=json.loads((OUT/'RESULTS_SUMMARY.json').read_text());rows=summ['arms'];by={r['arm']:r for r in rows};baseline=by['E0'];best=min(rows,key=lambda r:r['absolute_gap_from_100_pct_points']);bestate=min(rows,key=lambda r:r['ate_sim3_game_units'])
archives=json.loads((ROOT/'evidence/ALL_LOCAL_ARCHIVES_VERIFIED.json').read_text());assert len(archives)==8 and all(a['crc']=='PASS' for a in archives)
val=json.loads((OUT/'OFFLINE_ANALYSIS_VALIDATION.json').read_text());assert len(val['arms'])==8 and val['torch_imported'] is False
cleanupfile=ROOT/'remote_evidence/evidence/DATA_PRIORITY_SERVICE_CLEANUP.json'
cleanup=json.loads(cleanupfile.read_text()) if cleanupfile.exists() else None
assert cleanup and cleanup['owned_service_closed'] and not cleanup['ports_after'],'cleanup receipt incomplete'
head='# Task004A 八组因果筛选：结果与数据\n\n八组均完成，每组487帧、640×360、stride=1、buffer=500、seed=43，合计3896个有效导出位姿。每组仅运行一次，没有重试。\n\n'
header='|组|D/W/U|Sim3 ATE（游戏单位）|SE3 ATE（游戏单位）|全局尺度|312→328 位移比例 %|距100%的偏差（百分点）|关键帧|\n|---|---|---:|---:|---:|---:|---:|---:|\n'
table=header+''.join(f"|{r['arm']}|{r['D']}{r['W']}{r['U']}|{r['ate_sim3_game_units']:.6f}|{r['ate_se3_game_units']:.6f}|{r['global_fit_scale']:.6f}|{r['displacement_ratio_pct']:.3f}|{r['absolute_gap_from_100_pct_points']:.3f}|{r['keyframes']}|\n" for r in sorted(rows,key=lambda r:int(r['arm'][1:])))
interpret=f"\n固定RGB 312→328、冻结参考尺度下，距100%最近的是 **{best['arm']}**（{best['displacement_ratio_pct']:.3f}%）；本轮新跑的E0为 {baseline['displacement_ratio_pct']:.3f}%。全局Sim3 ATE最低的是 **{bestate['arm']}**（{bestate['ate_sim3_game_units']:.6f} 游戏单位）。这两种目标分别衡量指定区间位移与全段形状，不能互相替代。\n\n"
limits='D仅表示前端主循环局部BA的Metric3D正则是否参与，Metric3D预测与缓存仍在；W仅表示源端UBA权重；U仅表示该阶段是否更新U。初始化、Final BA及Filler保留原流程。\n\n固定RGB指标来自最终导出轨迹；直接关键帧指标只有端点都真实保留时才计算，缺失保持空值。没有用插值补造关键帧。端点尺度统一使用事先冻结的 s_ref=19.1341794347；ATE对每条完整487帧轨迹只拟合一次Sim3或SE3。GT仅供运行后本地评分，单位保留为游戏单位。\n\n每组一次、单序列、单种子：因子表是完整2³矩阵的描述性主效应与交互对比，没有重复运行误差估计或p值，不支持显著性、跨序列泛化或论文结论。关键帧及图结构随干预变化，因此结果是整条处理链的总效应，不是固定图、同状态BA的直接因果效应。负disparity统计包含同一位置在多次BA中的重复计数，不能称为独立异常像素总数。几何有效权重来自观测器CPU子采样复算，不能冒充完整CUDA权重场。\n\n'
visual='浏览器验证曾在E7失败，前三组模型均已成功完成。当时按旧规则暂停；随后用户明确要求暂不处理可视化、优先消融结果。本次保留E3/E4/E7而不重跑，按原顺序完成E0/E8/E6/E1/E2。后五组原生Rerun写入与算法配置仍保留，但没有宣称浏览器渲染通过。独立临时服务已退出；没有关机。\n'
text('TASK004A_ALL_RUNS_SUMMARY.md',head+table+interpret+limits+visual)
text('TASK004A_FINAL_CAUSAL_SCREENING_REVIEW.md',head+table+interpret+'下一步建议：先审查结果差异与关键帧留存，再决定是否批准Task004B的重复确认；本轮不自动进入Task004B或E5-F。\n\n'+limits+visual)
text('README_请先读.md','# 请先读\n\n本包是八组真实GPU消融后的结果和数据评审包。先读 TASK004A_FINAL_CAUSAL_SCREENING_REVIEW.md。evaluation/ 包含逐帧误差、RPE、三组目标区间、直接关键帧和最终导出的分离指标、BA时间线、U及disparity计数、因子效应。\n\nraw_trajectories/ 保存八组完整轨迹及关键帧身份；raw_run_receipts/ 保存运行、配置、策略、模型输出、stdout/stderr和退出码收据；完整 observer.jsonl 和原生 video.npz 位于本机 raw_archives/ 中的八个独立原始数据ZIP，清单为 RAW_DATA_ARCHIVE_INDEX.json。完整原始归档不重复塞入轻量包。\n\nFILE_SHA256_MANIFEST.json 覆盖包内全部有效载荷，自身不参与递归自校验；ZIP校验结果存于包外 PACKAGE_VALIDATION.json。所有指标的单位及尺度口径见评价合同。\n')
text('TASK004A_RESOURCE_REPORT.md','# 实际运行资源\n\n|组|模型进程耗时 s|峰值GPU总占用 MiB|BA调用|\n|---|---:|---:|---:|\n'+''.join(f"|{r['arm']}|{r['model_elapsed_s']:.3f}|{r['peak_gpu_used_mib']}|{r['ba_calls']}|\n" for r in rows)+'\nGPU指标为监控采样到的整卡占用，非torch单进程allocator峰值；耗时包含观测埋点与原生可视化写入，不能作为无观测器性能基准。服务器未关机。\n')
text('EVALUATION_CONTRACT.md','# 离线评价口径\n\n'+limits)
text('RERUN_STATUS_AND_AUTHORIZATION_CHANGE.md','# 本轮可视化状态\n\n'+visual)
rawindex=[{**a,'relative_path':'raw_archives/'+pathlib.Path(a['archive']).name} for a in archives];put(REPORT/'RAW_DATA_ARCHIVE_INDEX.json',rawindex)
put(REPORT/'SECURITY_AUDIT.json',dict(model_runs_consumed=8,max_runs_authorized=8,retries=0,additional_sequences=0,Task004B_started=False,E5F_started=False,production_source_modified=False,original_yaml_modified=False,model_weights_modified=False,cuda_extensions_recompiled=False,ground_truth_used_for_inference=False,remote_results_deleted=False,server_shutdown_performed=False,browser_render_gate_waived_by_user=True,native_rerun_writer_retained=True,owned_rerun_service_cleaned=cleanup['owned_service_closed']))
# A small data-driven SVG figure, using the same one-global-Sim3 alignment as CSV.
with (OUT/'TASK004A_PER_FRAME_TRAJECTORY_ERRORS.csv').open(encoding='utf-8-sig') as f:points=list(csv.DictReader(f))
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="660" viewBox="0 0 1200 660"><rect width="1200" height="660" fill="white"/><text x="24" y="28" font-family="Arial" font-size="20">Task004A: globally aligned X-Z trajectories (game units)</text>']
for n,arm in enumerate(sorted(by,key=lambda a:int(a[1:]))):
 a=[q for q in points if q['arm']==arm];xx=[float(q['aligned_x']) for q in a];zz=[float(q['aligned_z']) for q in a];lo=min(xx);hi=max(xx);lz=min(zz);hz=max(zz);span=max(hi-lo,hz-lz,1e-9);left=25+(n%4)*298;top=60+(n//4)*300
 xy=' '.join(f'{left+15+240*(x-lo)/span:.2f},{top+260-240*(z-lz)/span:.2f}' for x,z in zip(xx,zz));svg.append(f'<text x="{left}" y="{top}" font-family="Arial" font-size="16">{arm}; ATE {by[arm]["ate_sim3_game_units"]:.4f}; KF {by[arm]["keyframes"]}</text><polyline points="{xy}" fill="none" stroke="#2463a6" stroke-width="1.5"/>')
svg.append('<text x="24" y="646" font-family="Arial" font-size="12">Independent panel extents; use CSV for common-coordinate numeric comparison. One sequence, one seed per arm.</text></svg>')
text('TASK004A_TRAJECTORIES.svg',''.join(svg))
# Build a review directory without videos, RGB, weights, Chrome profiles or duplicate source repositories.
bundle=ROOT/'review_bundle';bundle.mkdir()
for q in REPORT.iterdir():shutil.copyfile(q,bundle/q.name)
for folder in ('evaluation','release/policies','tools'):
 dst=bundle/folder;dst.mkdir(parents=True,exist_ok=True)
 for q in (ROOT/folder).iterdir():
  if q.is_file() and q.suffix in ('.json','.csv','.md','.py','.svg','.txt'):shutil.copyfile(q,dst/q.name)
for arm in by:
 at=next((ROOT/'results'/arm).glob('attempt_*'));d=bundle/'raw_run_receipts'/arm;d.mkdir(parents=True)
 for q in at.iterdir():
  if q.is_file() and q.name!='observer.jsonl' and q.suffix in ('.json','.yaml','.txt'):shutil.copyfile(q,d/q.name)
 dst=bundle/'raw_trajectories'/arm;dst.mkdir(parents=True)
 for rel in ('trajectory.npz','keyframes.json','native/traj/est_poses_full.txt'):shutil.copyfile(at/rel,dst/pathlib.Path(rel).name)
for rel in ('AUTHORIZATION.txt','RESUME_AUTHORIZATION_DATA_PRIORITY.json','CAMPAIGN_STOP_DECISION.json','release/AUTHORIZATION.json','release/SOURCE_PINS.json','release/REFERENCE_FILES.json','release/RELEASE_SHA256.json','evidence/REMOTE_SEALED_ARCHIVE_RECEIPTS.json','evidence/ALL_LOCAL_ARCHIVES_VERIFIED.json','evidence/ALL_ARMS_LOCAL_TERMINAL_STATUS.json','evidence/OFFLINE_ANALYSIS_PROCESS_RECEIPT.json','evidence/offline_analysis.stdout.txt','evidence/offline_analysis.stderr.txt','evidence/resume_remaining.transport_receipt.json','evidence/resume_remaining.stdout.txt'):
 q=ROOT/rel;dest=bundle/'provenance'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(q,dest)
for n in ('DATA_PRIORITY_SERVICE_CLEANUP.json','ALL_EIGHT_RUNS_COMPLETE.json'):
 shutil.copyfile(ROOT/'remote_evidence/evidence'/n,bundle/'provenance'/n)
manifest={str(q.relative_to(bundle)).replace('\\','/'):{'sha256':sha(q),'bytes':q.stat().st_size} for q in bundle.rglob('*') if q.is_file()}
put(bundle/'FILE_SHA256_MANIFEST.json',dict(schema='TASK004A_FINAL_REVIEW_SHA256_V1',files=manifest,self_excluded=True,utc=utc()))
archive=ROOT/'GAMECAM_TASK004A_GPU_SCREENING_REVIEW.zip'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for q in sorted(bundle.rglob('*')):
  if q.is_file():z.write(q,str(q.relative_to(bundle)).replace('\\','/'))
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None;assert set(z.namelist())==set(manifest)|{'FILE_SHA256_MANIFEST.json'}
 for n,entry in manifest.items():assert hashlib.sha256(z.read(n)).hexdigest()==entry['sha256'] and len(z.read(n))==entry['bytes']
put(ROOT/'PACKAGE_VALIDATION.json',dict(package=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),zip_crc='PASS',internal_sha256_matches=len(manifest),raw_archives_verified=8,raw_payload_sha256_matches=sum(a['internal_sha256_matches'] for a in archives),utc=utc()))
print('PACKAGE_COMPLETE',str(archive),flush=True);print(json.dumps({'arms':rows,'package_bytes':archive.stat().st_size},ensure_ascii=False),flush=True)