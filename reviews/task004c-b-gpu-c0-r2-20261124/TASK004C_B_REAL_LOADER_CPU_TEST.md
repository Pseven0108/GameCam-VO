# 真实Loader CPU验证与历史回归

最终结果：新增 **21/21 PASS**，原有 **152/152 PASS**，合计173个通过用例。真实连续RGB001～018共18帧，使用原RGB_NoPose父类、原RGB、原INPUT manifest与原R2预处理。

新测试耗时1.178秒；最终152项耗时37.775秒。CPU过程CUDA未初始化、无checkpoint加载、无GT读取、无GPU运行。

覆盖：RGB001解码；零占位接受；原tuple/对象身份保持；depth=None拒绝；非零/NaN/Inf；pose非None；depth shape/dtype；非CPU(meta)；RGB shape；timestamp及bool；错误Frame ID；标签源在父类读取前拒绝；失败seen不前进；跳帧和越界拒绝；连续18帧。

## 首轮回归缺失测试资产

第一次152项结果为151通过、1 ERROR，原因是独立目录缺少`source_before/src/depth_video.py`，并非断言发现BA变化。没有跳过或修改该断言。

已从完整历史提交0931141导出这一原始对照文件，SHA=`cb668fab8f2d78c73e0e34efad6c561b9acdbe57df0463b79bd1407e1bfb1f48`，与前轮评审preimage一致。保留首次失败记录，再完整重跑152项全部通过后才发布GPU准入。

前期另有Git作者元数据未配置导致的提交失败；只在独立克隆中恢复作者元数据，没有改算法或环境。此事不是CPU用例失败或GPU重试。

## 原始证据

- `remote_evidence/artifacts/REAL_LOADER_CPU/CPU_TEST_REPORT.json`：21项逐项stdout/stderr/exit及SHA。
- `RGB001_018_MANIFEST.json`：原文件SHA、处理后RGB逻辑SHA、shape/dtype、游标。
- `RELEASE_CPU_c0_r2/CPU_TEST_REPORT.json`：首轮151/152记录。
- `RELEASE_CPU_c0_r2_ready/CPU_TEST_REPORT.json`：最终152/152记录。
- `remote_evidence/evidence/CPU_PHASE_FINAL_DECISION.json`：组合准入决定。

每个test的exit_code为unittest结果映射；套件实际OS子进程退出码和stdout/stderr另存在PROCESS_RESULT.json。没有把每个unittest用例伪称为独立OS进程。
