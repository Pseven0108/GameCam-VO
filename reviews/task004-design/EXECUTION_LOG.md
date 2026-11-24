# Task 004｜本地执行记录

本阶段按用户最新的 Task004 附件执行。工作目录：D:/aaa/GameCam-VO/experiments/DROID_W_TASK004_CAUSAL_ABLATION。冻结源码、原 R2、Task003 与旧结果只读；候选文件、测试输出和归档写在本目录内。没有远端操作、没有 GPU/CUDA/模型调用、未安装包和未重编译扩展。

| 实际步骤 | 退出码 | 证据 |
| --- | ---: | --- |
| Task001 静态核验工具只读重验冻结源码、blob 和 gitlink | 0 | logs/verify_frozen_sources.stdout.txt、stderr.txt、exit.txt |
| 构建候选：核验 Task003、补丁可应用、后像逐字节核对 | 0 | logs/prepare_release.stdout.txt、stderr.txt、exit.txt |
| 最终隔离 CPU Mock：16/16 | 0 | logs/cpu_mock_release.stdout.txt、stderr.txt、exit.txt |
| 历史引用指纹复核及归档封存 | 见外部回执 | ZIP_VALIDATION.json 核验 ZIP CRC、所有包内 SHA-256、矩阵策略 SHA、源文件和历史引用。 |

CPU Mock 使用本机已安装运行时 Python 3.12 和 NumPy；Python 子进程 CUDA_VISIBLE_DEVICES 为空，OMP_NUM_THREADS=2，OPENBLAS_NUM_THREADS=1，MKL_NUM_THREADS=1。未导入 torch 或 DROID-W 模型。测试通过 AST 取出实际候选方法，用 CPU 替身替代 native BA、模型和缓冲区；不能当成 CUDA 运行成功。

早期记录保留：首次生成误把 loop 备用路径纳入两个可达观测调用点的计数，构建守卫因此退出；首轮 Mock 缺少 depth-mask 替身方法，初步版修正通过 15 项。扩充统计的重建阶段遇到新后像和已有候选重名，以及矩阵防覆盖错误，均停止；旧候选副本保存在本地 evidence/initial_candidate，矩阵生成改为验证与既有字节一致。最终复核以上表 release 版本为准。轻量包收录原始测试和构建日志。
