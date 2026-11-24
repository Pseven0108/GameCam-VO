"""Generate Task004B reports and review archives after all sixteen GPU runs and CPU checks."""
import pathlib,sys,os,json,csv,math,hashlib,zipfile,shutil,collections
from datetime import datetime,timezone
from analyze_repeated import ROOT,AROOT,OUT,c,ARMS,put,csvout,sha,UTC
R=ROOT/'reports'
def text(name,s):
 p=R/name
 with p.open('x',encoding='utf-8') as f:f.write(s)
def rcsv(p):
 with pathlib.Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def n(x,k):return float(x[k]) if x[k] not in ('',None) else None
def fmt(x,places=3):return '不可得' if x is None else f'{x:.{places}f}'
def table(headers,rows):return '|'+ '|'.join(headers)+'|\n|'+'|'.join('---' for _ in headers)+'|\n'+''.join('|'+ '|'.join(str(v) for v in row)+'|\n' for row in rows)
def main():
 assert (OUT/'TASK004B_RESULTS.json').is_file()
 assert (ROOT/'evidence/FINAL_REMOTE_PRESERVATION.json').is_file(),'final read-only preservation check required'
 d=json.loads((OUT/'TASK004B_RESULTS.json').read_text());rows=d['runs'];assert len(rows)==24
 f=d['effects'];summ=d['arm_summaries'];new=[r for r in rows if r['seed']!=43]
 archive=json.loads((ROOT/'evidence/ALL_LOCAL_ARCHIVES_VERIFIED.json').read_text());assert len(archive)==16
 pres=json.loads((ROOT/'evidence/FINAL_REMOTE_PRESERVATION.json').read_text());assert pres['mismatches']==[] and pres['campaign_complete'] and pres['stop'] is None
 R.mkdir(exist_ok=True)
 def effect(metric,factor):return next(x for x in f if x['metric']==metric and x['factor']==factor)
 def ss(arm,metric):return next(x for x in summ if x['arm']==arm and x['metric']==metric)
 def evrow(metric,factor):
  q=effect(metric,factor);return [metric,factor,fmt(q['seed43_effect']),fmt(q['seed44_effect']),fmt(q['seed45_effect']),fmt(q['mean']),f"[{fmt(q['ci95_low'])}, {fmt(q['ci95_high'])}]",'是' if q['same_nonzero_direction'] else '否']
 def eftable(metrics,factors=('D','W','U','D:W','D:U','W:U','D:W:U')):return table(['指标','因素','Seed43','Seed44','Seed45','均值','95% CI','同号'],[evrow(metric,factor) for metric in metrics for factor in factors])
 runstable=table(['Seed','组','D/W/U','Sim3 ATE','SE3 ATE','全局拟合尺度','312→328比例%','距100%偏差pp','KF','秒'],[[r['seed'],r['arm'],f"{r['D']}{r['W']}{r['U']}",fmt(r['ate_sim3_game_units']),fmt(r['ate_se3_game_units']),fmt(r['global_fit_scale']),fmt(r['displacement_ratio_pct']),fmt(r['absolute_gap_from_100_pct_points']),r['keyframes'],fmt(r['model_elapsed_s'],1)] for r in rows])
 armstable=table(['组','D/W/U','Sim3 ATE 均值±SD','312→328比例% 均值±SD','端点偏差pp 均值±SD','KF 均值±SD'],[[arm,''.join(map(str,c.BITS[arm])),f"{fmt(ss(arm,'ate_sim3_game_units')['mean'])} ± {fmt(ss(arm,'ate_sim3_game_units')['sd'])}",f"{fmt(ss(arm,'displacement_ratio_pct')['mean'])} ± {fmt(ss(arm,'displacement_ratio_pct')['sd'])}",f"{fmt(ss(arm,'absolute_gap_from_100_pct_points')['mean'])} ± {fmt(ss(arm,'absolute_gap_from_100_pct_points')['sd'])}",f"{fmt(ss(arm,'keyframes')['mean'],1)} ± {fmt(ss(arm,'keyframes')['sd'],1)}"] for arm in ARMS])
 intro='# Task004B 重复因子消融：完整结果\n\n新增 Seed44、Seed45 共16/16次真实 GPU 运行完成；复用 Seed43 的8次历史运行，得到24次完整结果，每组3次观测重复。全部487帧导出有效，共11,688个最终位姿；其中本轮新增7,792个。没有自动重试、跳组、额外种子或 Task004C。\n\n固定 val_007、640×360、stride=1、buffer=500。D/W/U 仅干预前端 main-loop local BA；初始化、Final BA 和 Filler 保持原流程。量纲为游戏单位，不假定米。估计对象是 TOTAL_FRONTEND_EFFECT。\n\n'
 caveat='\n\n**种子与统计限制：** 原生 setup_seed 在主进程设置种子；spawn 跟踪子进程没有额外统一设种子调用。本轮保留原生行为，并保存主进程与跟踪入口的 RNG 收据。因此这是三个“配置种子区组”的实际重复，不能称为所有随机源都受控的完全确定性实验。n=3；95% CI 使用三个区组的对比值和 t(df=2)，是小样本、未做多重校正的描述性区间。单次运行的像素和 BA 事件均不当作独立样本。 同种子配对表示同一配置种子区组内的条件差值，不代表跟踪子进程共享同一RNG状态，不能当作共同随机数的严格配对。\n\n**评价限制：** 固定端点比例使用冻结 s_ref=19.1341794347；Sim3 ATE 每条轨迹只拟合一个全局尺度。SE3 ATE 不缩放。比例接近100%不自动意味着方向正确，需同时读取方向误差与 RPE。直接关键帧缺失保持不可得，不用 Filler 或插值替代。\n'
 text('TASK004B_ALL_RUNS_SUMMARY.md',intro+armstable+'\n\n'+runstable+caveat)
 metric_names=('ate_sim3_game_units','absolute_gap_from_100_pct_points','displacement_ratio_pct','keyframes')
 text('TASK004B_STATISTICAL_REPORT.md','# 三种子区组统计\n\n模型为 y(seed,D,W,U)=种子区组截距 + 7项完整因子效应 + 残差。±1编码的回归系数为报告效应的一半；效应定义为每个种子内 sum(符号乘积 × y)/4，再对三个种子做汇总。完整线性模型24行、秩10、残差自由度14，用于算术交叉核对；报告区间来自三个种子效应，不使用像素或事件的样本量。\n\n'+eftable(metric_names)+caveat+'\n条件D对比、每组均值/中位数/SD/最小最大、逐种子差值与区间均在CSV中。D_ON_MINUS_D_OFF为固定W/U下D=1减D=0；ARM_MINUS_E0为同种子内该组减E0。正负方向需结合指标意义解释。\n')
 ratios=effect('displacement_ratio_pct','D');gap=effect('absolute_gap_from_100_pct_points','D');ate=effect('ate_sim3_game_units','D');kf=effect('keyframes','D')
 conditional=rcsv(OUT/'TASK004B_SEEDWISE_PAIRED_DIFFERENCES.csv')
 d12=[q for q in conditional if q['comparison']=='D_ON_MINUS_D_OFF' and q['metric']=='ate_sim3_game_units'];g12=[q for q in conditional if q['comparison']=='D_ON_MINUS_D_OFF' and q['metric']=='absolute_gap_from_100_pct_points'];k12=[q for q in conditional if q['comparison']=='D_ON_MINUS_D_OFF' and q['metric']=='keyframes'];s12=[q for q in conditional if q['comparison']=='D_ON_MINUS_D_OFF' and q['metric']=='ate_se3_game_units']
 counts=dict(sim3_Doff_lower=sum(n(q,'paired_difference')>0 for q in d12),endpoint_Doff_lower=sum(n(q,'paired_difference')>0 for q in g12),kf_Doff_more=sum(n(q,'paired_difference')<0 for q in k12),conditional_pairs=12,se3_Doff_lower=sum(n(q,'paired_difference')>0 for q in s12))
 d_supported=ate['same_nonzero_direction'] and ate['mean']>0 and gap['same_nonzero_direction'] and gap['mean']>0
 k_supported=kf['same_nonzero_direction'] and kf['mean']<0
 text('TASK004B_FINAL_RESEARCH_REVIEW.md',intro+'## 研究判断\n\n'+
 f"1. **关闭D是否稳定改善轨迹与固定端点误差：{'本序列三配置种子区组支持' if d_supported else '并非所有主要结局都得到同方向支持，需逐项解释'}。** D=1减D=0的Sim3 ATE效应为 {fmt(ate['mean'])}，95% CI [{fmt(ate['ci95_low'])}, {fmt(ate['ci95_high'])}]；固定端点距100%的偏差效应为 {fmt(gap['mean'])} pp，95% CI [{fmt(gap['ci95_low'])}, {fmt(gap['ci95_high'])}]。12个固定W/U、同区组条件对比中，关闭D后Sim3 ATE较低 {counts['sim3_Doff_lower']}/12，固定端点偏差较低 {counts['endpoint_Doff_lower']}/12。\n\n"+
 f"2. **不能把所有D=1运行一概叫作平移压缩。** D的有符号位移比例效应为 {fmt(ratios['mean'])} pp，三个区组分别为 {fmt(ratios['seed43_effect'])}、{fmt(ratios['seed44_effect'])}、{fmt(ratios['seed45_effect'])}；D/W/U组合存在异质性。距离100%的偏差与方向/RPE比单看比例的增减更适合判断改善。\n\n"+
 f"3. **关键帧选择改变：{'得到三配置种子区组同方向支持' if k_supported else '结果存在方向差异或证据不足'}。** D=1减D=0的KF数量效应 {fmt(kf['mean'])}，95% CI [{fmt(kf['ci95_low'])}, {fmt(kf['ci95_high'])}]；12个条件对比中，关闭D后KF更多 {counts['kf_Doff_more']}/12。逐帧Motion Filter、Predecision BA、Local BA拒绝和最终保留表均已保留。\n\n"+
 '4. **D是否“通过”Predecision BA导致全部轨迹变化：尚未建立纯中介因果证明。** 干预范围包含Predecision和Retained两个前端阶段，运行间图、关键帧和后续优化输入随之变化。时间线支持完整前端机制的过程证据，但没有固定状态直接效应实验，不能把总效应归于某一次BA或唯一中介。\n\n'+
 '5. **交互作用：** 下表逐指标报告D×W、D×U等效应，方向相同仅表示本序列三重复中的方向稳定，不等同于普遍交互规律。\n\n'+eftable(('ate_sim3_game_units','absolute_gap_from_100_pct_points','keyframes'),('D:W','D:U','W:U','D:W:U'))+
 f'\n**不能将上述形状/端点收益外推为原生尺度整体精度提升：** 12个条件对比中关闭D后SE3 ATE较低 {counts["se3_Doff_lower"]}/12。应结合SE3、全局尺度和四个offset的RPE共同阅读，保留不一致结局。\n'+
 '\n6. **下一阶段建议：** 优先据D的条件效应、端点方向/RPE和关键帧选择共同制定最小验证问题。若要区分直接BA效应和关键帧/后续优化传播效应，需要单独审批固定状态实验。当前不实施修复、不进入Task004C，不声称跨场景泛化或论文创新已得到证明。\n'+caveat+'\n本轮阶段状态：TASK004B_COMPLETE_WAITING_FOR_REVIEW。服务器保持当前状态，未关机。\n')
 put(R/'TASK004B_RESEARCH_DECISIONS.json',dict(Doff_supported_on_primary_error_and_sim3=d_supported,keyframe_increase_supported=k_supported,conditional_counts=counts,total_frontend_effect_only=True,pure_direct_effect_established=False,mediator_causality_established=False,cross_environment_generalization_established=False))
 text('TASK004B_PROTOCOL_AND_MEASUREMENT.md','# 冻结协议与测量定义\n\n- DROID-W commit：'+c.COMMIT+'。\n- 原R2 YAML SHA256：'+c.CONFIG_SHA+'。仅运行内存中的setup_seed按44/45设置；保存的原YAML字节未更改。\n- 487帧RGB输入、640×360、stride=1、buffer=500，模型输入没有GT位姿。GT只进入本地CPU离线评价。\n- D=0仅不向指定局部BA传入缓存Metric3D先验；不停止模型预测/缓存。W=0禁用源端UBA，U=0停止对应局部U更新。目标端门控、初始化、Final BA、Filler保持既有合同。\n- 全局Sim3/SE3公式、四个RPE offset、三个固定端点区间均复用Task004A代码。Seed43的48项关键复算值与原交付逐项匹配。\n- U_event_medians_median是每次局部BA采样U中位数的运行内中位数；P90/P95同理。不是将全视频全部像素汇集后计算的分位数。Effective weight来自已记录的确定性CPU边/像素子采样，不代表捕获全部CUDA权重场。\n- 负disparity/floor像素事件会在多次BA中重复计数，不是独立像素数。clamp_pixel_events_from_new_floor按每次native-after与clamp-after的floor数量增量累计，是新变成floor的像素事件数，仍会重复计入同一空间位置。clamp_calls_changing_grid仅统计观测前后计数结构发生改变的调用；不能解释为唯一被clamp的像素数。\n- Motion filter分数是既有delta的CPU norm代理；frontend_distance是记录的原生距离标量。两者不混同。\n- Local candidate rejection rate分母为出现Predecision BA的不同候选RGB帧，原始决策和完整调用CSV另附。\n')
 configrows=[];rerunrows=[];rid=[]
 baseline=next((AROOT/'results/E0').glob('attempt_*'))/'native_config.yaml'
 def normal_cfg(path):
  return [line for line in path.read_text().splitlines() if not line.strip().startswith(('setup_seed:','output:'))]
 expected_cfg=normal_cfg(baseline)
 for rr in rows:
  src=AROOT if rr['seed']==43 else ROOT;at=next((src/'results'/('seed'+str(rr['seed']) if rr['seed']!=43 else '')/rr['arm']).glob('attempt_*'))
  assert normal_cfg(at/'native_config.yaml')==expected_cfg
  configrows.append(dict(seed=rr['seed'],arm=rr['arm'],native_config_sha256=sha(at/'native_config.yaml'),reference_yaml_sha256=c.CONFIG_SHA,algorithm_config_equivalence='PASS_EXCLUDING_ONLY_SETUP_SEED_AND_OUTPUT_PATH',setup_seed=rr['seed']))
  if rr['seed']!=43:
   rv=json.loads((at/'RERUN_RECORDING_VALIDATION.json').read_text());assert rv['decode_exit_code']==0 and len(rv['recording_ids'])==1;rid.extend(rv['recording_ids']);rerunrows.append(dict(seed=rr['seed'],arm=rr['arm'],**rv))
 assert len(rid)==16 and len(set(rid))==16
 csvout(OUT/'TASK004B_RUNTIME_CONFIG_EQUIVALENCE.csv',configrows)
 csvout(OUT/'TASK004B_RERUN_RECORDING_SUMMARY.csv',rerunrows)
 seedrows=[]
 for r in new:
  at=next((ROOT/'results'/('seed'+str(r['seed']))/r['arm']).glob('attempt_*'))
  for file in ('seed_receipt_main.json','seed_receipt_tracking_spawn_entry.json'):
   q=json.loads((at/file).read_text());seedrows.append(dict(seed=r['seed'],arm=r['arm'],**q))
 csvout(OUT/'TASK004B_SEED_CONTROL_RECEIPTS.csv',seedrows)
 text('TASK004B_SEED_AND_RERUN_LIMITATIONS.md','# 随机源与原生记录\n\n原始主进程setup_seed设置Python、NumPy、PyTorch和CUDA种子；跟踪spawn入口未统一重新设种子。收据记录实际RNG状态，未为收据额外抽样。主进程和子进程的cudnn标志可能不同，完整保留原生行为，未附加新的deterministic/benchmark设置。\n\n每组原生Rerun writer保持开启；本轮增加服务端独立.rrd保存和原生解码核验，每组唯一recording ID。Seed43历史归档没有.rrd，不伪造历史记录。服务端录制增加I/O开销；因此跨区组runtime不应被当作纯模型耗时差异。浏览器实时渲染未核实，且用户已取消该项作为GPU启动门槛。\n\nRerun服务在模型正常完成后由本次控制器终止，服务退出码-15代表受控SIGTERM；模型退出码独立记录为0。停止服务后再用原生rrd print检查可解码性；这证明文件可解码，不证明浏览器看到了全部对象。\n')
 text('TASK004B_ARCHIVE_AND_REPRODUCIBILITY.md','# 原始资产与复算\n\n完整的16个新增逐运行ZIP保存在本目录raw_archives，包含observer、native/video.npz、native_rerun.rrd、配置、轨迹、日志和运行收据；每个文件已逐个CRC、SHA256、大小核验。Seed43的8份历史ZIP原位保留。外部原始ZIP索引见TASK004B_RAW_ARCHIVE_INDEX.csv。\n\n轻量评审包包含最终报告、全部汇总和必要逐帧表、配置、收据和轨迹；完整评审包另加入24次observer及resource原始日志和完整衍生事件表。为避免重复数GB原始数据，native/video.npz和.rrd仍在逐运行完整原始ZIP中，其SHA与成员索引随评审包提供。没有删除远端产物。\n\nCPU复算入口：tools/analyze_repeated.py；统计入口：tools/summarize_repeated.py。依赖原Task004A的已校验公式模块及本地GT，不导入torch，不执行GPU工作。执行脚本、版本SHA、输出校验和退出码均附在证据目录。\n')
 text('README_请先读.md',intro+'先阅读TASK004B_FINAL_RESEARCH_REVIEW.md，再看TASK004B_ALL_RUNS_SUMMARY.md和TASK004B_STATISTICAL_REPORT.md。\n\n'+armstable+caveat+'\n轻量包适合GPT聊天版评审，完整包包含原始观测日志。原始深度缓存和Rerun记录完整保留在16份逐运行ZIP中，见归档索引。\n')
 security=dict(gpu_used=True,gpu_restarted=False,cuda_context_initialized=True,checkpoint_deserialized=True,model_forward_executed=True,real_slam_executed=True,additional_real_gpu_runs=16,previous_seed43_runs_reused=8,each_new_run_attempts=1,retries=0,run_order_confirmed=pres['order_match'],all_model_exit_codes_zero=all(r['status']=='COMPLETE' for r in rows),training_performed=False,other_sequence_executed=False,new_seeds_beyond_44_45=False,E5F_executed=False,Task004C_executed=False,fixed_state_experiment_executed=False,model_weights_modified=False,original_yaml_modified=False,production_sources_modified=False,cuda_extension_recompiled=False,remote_results_deleted=False,github_push_performed=False,server_shutdown_performed=False,browser_verified=False,all_pinned_paths_verified=len(pres['verified']),pin_mismatches=pres['mismatches'],gt_used_in_inference=False)
 put(R/'SECURITY_AUDIT.json',security)
 text('EXECUTION_LOG.md','# 执行记录\n\n正式运行依照release/AUTHORIZATION.json的固定顺序，Seed44正序、Seed45反序。各运行独立attempt_001，无自动重试。模型启动、资源轮询、终态、封存、下载、CPU评价各有收据。\n\nCPU准备阶段曾有本地/远端脚本语法错误，均发生在正式模型启动之前，修正后才发布；原始prepare证据保留，不计为GPU重试。\n\n'+table(['Seed','组','Attempt','模型退出码','秒','显存峰值MiB','shm峰值bytes'],[[r['seed'],r['arm'],r['attempt_id'],0,fmt(r['model_elapsed_s'],2),r['peak_gpu_used_mib'],r.get('peak_shm_used_bytes','历史未记录')] for r in rows])+'\n最后远端只读保护核验、控制器终态、无重试和每个本地归档的CRC/SHA结果见evidence。\n')
 # External raw archive identities, including previous Seed43.
 raws=[]
 for rec in json.loads((AROOT/'evidence/ALL_LOCAL_ARCHIVES_VERIFIED.json').read_text()):raws.append(dict(seed=43,**rec))
 raws.extend(archive)
 csvout(OUT/'TASK004B_RAW_ARCHIVE_INDEX.csv',[{k:v for k,v in q.items() if k not in ('files',)} for q in raws])
 topnames=['TASK004B_SEED44_RESULTS.csv','TASK004B_SEED45_RESULTS.csv','TASK004B_24_RUN_MASTER_TABLE.csv','TASK004B_FACTORIAL_EFFECTS.csv','TASK004B_KEYFRAME_RETENTION_ANALYSIS.csv','TASK004B_FIXED_ENDPOINT_COMPARISON.csv','TASK004B_LOCAL_BA_TIMELINE_COMPARISON.csv','TASK004B_UNCERTAINTY_INTERACTION_ANALYSIS.csv','TASK004B_ATE_RPE_COMPARISON.csv']
 for fn in topnames:shutil.copyfile(OUT/fn,R/fn)
 payload={}
 def add(path,name):
  assert name not in payload,(name,path);payload[name]=pathlib.Path(path)
 for p in R.iterdir():
  if p.is_file():add(p,p.name)
 for p in OUT.iterdir():
  if p.is_file():add(p,'evaluation/'+p.name)
 for p in (ROOT/'tools').glob('*.py'):add(p,'tools/'+p.name)
 for p in (ROOT/'release').rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:add(p,'release/'+p.relative_to(ROOT/'release').as_posix())
 # Include small final evidence, release/protection and process/transport receipts.
 for p in (ROOT/'evidence').iterdir():
  if p.is_file() and not p.name.startswith(('watch_','status_')) and p.stat().st_size<2*1024**2:add(p,'evidence/'+p.name)
 for r in rows:
  src=AROOT if r['seed']==43 else ROOT;folder=src/'results'/('seed'+str(r['seed']) if r['seed']!=43 else '')/r['arm'];at=next(folder.glob('attempt_*'));prefix=f"raw_runs/seed{r['seed']}/{r['arm']}/"
  for p in at.iterdir():
   if p.is_file() and p.name not in ('observer.jsonl','resource.jsonl','native_rerun.rrd','rerun_recording_print.txt') and p.suffix in ('.json','.yaml','.txt','.npz'):add(p,prefix+p.name)
  for rel in ('native/traj/est_poses_full.txt','native/timer_summary.csv'):
   if (at/rel).is_file():add(at/rel,prefix+rel)
  val=OUT/'runs'/('seed'+str(r['seed'])+'_'+r['arm'])/'VALIDATION.json';add(val,prefix+'CPU_VALIDATION.json')
 for pp in (ROOT/'remote_evidence').rglob('*'):
  if pp.is_file():add(pp,'remote_evidence/'+pp.relative_to(ROOT/'remote_evidence').as_posix())
 for rr in ('contracts.py','endpoints.py','trace_audit.py'):
  add(AROOT/'release/tools'/rr,'reference_math/'+rr)
 add(AROOT/'tools/offline_analyze.py','reference_math/offline_analyze.py')
 full=dict(payload)
 for r in rows:
  src=AROOT if r['seed']==43 else ROOT;at=next((src/'results'/('seed'+str(r['seed']) if r['seed']!=43 else '')/r['arm']).glob('attempt_*'))
  for name in ('observer.jsonl','resource.jsonl'):
   if (at/name).is_file():full[f"raw_runs/seed{r['seed']}/{r['arm']}/{name}"]=at/name
 # Lightweight reader excludes large per-event derivative tables only; all numeric summaries retained.
 light={n:p for n,p in payload.items() if not (n.startswith('evaluation/') and pathlib.PurePosixPath(n).name in {'TASK004B_LOCAL_BA_TIMELINE_COMPARISON.csv','TASK004B_UNCERTAINTY_EVENTS.csv','TASK004B_DISPARITY_EVENTS.csv'}) and n!='TASK004B_LOCAL_BA_TIMELINE_COMPARISON.csv'}
 def pack(name,entries):
  manifest={n:dict(sha256=sha(p),bytes=p.stat().st_size) for n,p in sorted(entries.items())};doc=dict(schema='GAMECAM_TASK004B_REVIEW_SHA256_V1',utc=UTC(),files=manifest,self_excluded=True)
  path=ROOT/name
  with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
   for n,p in sorted(entries.items()):z.write(p,n)
   z.writestr('FILE_SHA256_MANIFEST.json',json.dumps(doc,ensure_ascii=False,indent=2))
  verified=0
  with zipfile.ZipFile(path) as z:
   assert z.testzip() is None;assert set(z.namelist())==set(manifest)|{'FILE_SHA256_MANIFEST.json'}
   for n,v in manifest.items():
    h=hashlib.sha256();size=0
    with z.open(n) as f:
     while data:=f.read(2**20):h.update(data);size+=len(data)
    assert h.hexdigest()==v['sha256'] and size==v['bytes'];verified+=1
  result=dict(path=str(path),sha256=sha(path),bytes=path.stat().st_size,crc='PASS',internal_sha256_verified=verified)
  put(ROOT/(name+'.verification.json'),result);print(json.dumps(result),flush=True);return result
 lightrec=pack('GAMECAM_TASK004B_REVIEW_LIGHT_FOR_GPT.zip',light)
 fullrec=pack('GAMECAM_TASK004B_CONFIRMATORY_REVIEW.zip',full)
 put(ROOT/'TASK004B_DELIVERY.json',dict(status='TASK004B_COMPLETE_WAITING_FOR_REVIEW',archives=[lightrec,fullrec],new_gpu_runs=16,total_runs=24,unit='GAME_UNITS',no_shutdown=True,utc=UTC()))
 print('TASK004B_REVIEW_DELIVERABLES_COMPLETE',flush=True)
if __name__=='__main__':main()
