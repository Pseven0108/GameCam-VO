# 证据读取与复核

GT仅本地离线：val_007.npz SHA256 91fb149c066bb488ac6071602a4b50fe1540243f2db3369a3706f63b705d7008；RGB1–487对应Camera0–486。源、权重、配置、C0最终核验见FINAL_ASSET_PRESERVATION.json。

成功组：raw_evidence/R3_OFFLINE/attempts/B1、B2、B4、B3。每组有PROCESS_RECEIPT、SUCCESS、RESTORE_RECEIPT、STAGE_RESUME_INPUT、配置、轨迹、调度、观测日志与stdout/stderr。R2早期工程失败保留在独立namespace，不能混入成功组。

大JSONL按约32MiB未压缩内容无损gzip分块。各chunks.json列出顺序、SHA、字节数；依次解压并拼接，核验public_log_sha256。SSH主机名、实例标识和run token被隐藏时，公开内容hash与本地originalhash分别记录；没有删BA事件。建议逐行读取，避免一次展开全部JSON对象。

FILE_SHA256_MANIFEST覆盖除清单自己以外全部ZIP成员；ZIP整体SHA覆盖清单，避免自哈希循环。PUBLICATION_SANITIZATION_MAP追溯脱敏变化；PUBLICATION_EXCLUSIONS列出本地保留大payload及hash，不意味着它们被上传。

analysis/offline_crossover_r3.py为NumPy CPU评价，--selfcheck包含13项已知Sim3、SE3、四元数、端点缺失、尺度规范一致性与严格JSON检查。完整评价需本地GT与video.npz，公开包缺少这些payload，不能声称只凭公开包完整复跑所有数值。

最终执行收据：R3_FINAL_CPU_OFFLINE_EVALUATION_03.receipt.json。首次JSON标量失败与第二次本机画图库缺失的stderr/退出码保留；最终exit0，未重跑模型。独立本机绘图库版本见R3_CPU_PLOT_ENVIRONMENT.json。

资源为约5秒采样，不保证捕获瞬时峰值。设备显存包括Rerun和开销，非单模型allocator精确峰值；B1监控从运行中途开始，峰值仅已观察下界。存储安全线偏离完整公开。

ZIP关机前封存，SECURITY_AUDIT记录当时未执行。实际shutdown命令及可达性观察将以独立GitHub材料追加，不改写已封存ZIP。
