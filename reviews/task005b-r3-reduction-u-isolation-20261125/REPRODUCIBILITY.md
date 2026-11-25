# 重现入口

唯一状态D0_S1_RGB233的state SHA：90f436de0f6139dc013fd545aeb047fe0ed28b649a6d2e811f8e15fbfa35b791。
原输入tar SHA：906ee063eb919d6ccc70c28fa01d5542f96ac0692f63873582c3ef8950b19891。
固定中间态：R2 results/trace/trace_reference_1.npz，SHA 05425393e11cfb025a2b2e95234809e1f4b11ef39e29fe658d8f1912bf64b7b5。

1. 阅读PROTOCOL.md与METHOD_AND_LIMITATIONS.md。
2. 02_candidate/generate_r3.py生成独立源副本；R1 kernel正文保留。
3. 03_tests/test_source_contract.py核验接口与干预位置。
4. 02_candidate/build_r3.py独立编译gamecam_task005b_r3_isolation，不替换原.so。
5. 01_runtime/replay_r3.py为本轮GPU唯一执行入口，预算32个孤立kernel调用及20次双迭代BA，完成不可自动重跑。
6. 04_analysis/analyze_isolated.py、analyze_ba.py、verify_feedback_math.py只用CPU分析封存原始NPZ。路径在脚本开头明确，迁移时应另存配置而不是修改历史证据。
7. 03_tests/run_all_recorded.py记录全部回归测试stdout/stderr和退出码。
8. 完整ZIP包含原输入tar、R2固定中间态、52份原始NPZ、诊断.so、全部运行日志与源码。GitHub展开目录保留报告和CSV，原始大数组在ZIP内。

CPU公式检查借用的R2字节读取器及其导入依赖另存于04_analysis/historical_R2_dependencies，保留原文。脚本中的历史绝对路径是本次执行路径，不保证解压后直接可运行；迁移复算应创建独立工作副本，令DATA对应raw/results、输入tar对应raw/input/snapshot_D0_S1_RGB233.tar、R2中间态对应raw/input/R2_trace_reference_1.npz，并调整CPU NumPy依赖路径。不要为复算自动执行任何GPU入口。原保护集记录外部权重及配置身份，本ZIP不分发模型权重。

运行环境：既有PyTorch 2.1/CUDA11.8环境，RTX3090（compute capability8.6）；准确版本、编译选项、extension SHA见INPUT_IDENTITY与build收据。原配置、权重、原扩展与R1/R2均不改。本地分析不导入PyTorch，CUDA_VISIBLE_DEVICES为空。

源码、GPU调用实参与原始输出是当前结论的依据；进程退出成功本身不等于端点准入成功。无模型加载/训练，无RGB输入序列，无S0扩展，无新深度机制矩阵。
