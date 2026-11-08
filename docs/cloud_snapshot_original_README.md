# GameCam-VO

动态游戏视频相机运动实验工程，复用现有项目和 Conda 环境。
当前数据策略为 MVS-Synth（GTA V）首先启动、OmniWorld-Game 随后接入，
WildWorld 保留并等待作者批准。当前真实数据和指标状态见 reports/00_project_status.md。

第四阶段的最新进度以 [SOTA 当前状态](reports/SOTA/CURRENT_STATE.md) 为准；
[同输入横向评价](reports/SOTA/E11_comparison_report.md) 与
[下一阶段研究判断](reports/SOTA/E12_research_direction_status.md) 单独记录。
三个近期方法分别使用独立 WSL Conda 环境，原 Windows gamecam-vo 环境保留。

## Environment

Conda 环境名 gamecam-vo，Python 3.11。E0/E1-A 使用 CPU，无需 PyTorch。

    conda activate gamecam-vo
    cd D:\aaa\GameCam-VO
    python scripts/collect_environment.py
    python scripts/run_tests.py

重建环境：

    conda create -n gamecam-vo python=3.11 pip -y
    conda run -n gamecam-vo python -m pip install -r requirements-lock.txt

requirements-lock.txt 固定本次 pip 依赖；environment-win64-explicit.txt 记录
Windows Conda 包的具体构建；environment.yml 与 requirements.txt 是维护入口。
不升级或修改其他已有环境。

## Public datasets: current primary workflow

配置分别在 configs/datasets/mvs_synth.yaml、omniworld_game.yaml、wildworld.yaml。
datasets/ 下按数据集实现 GameCameraDataset 统一接口，旧 WildWorld 模块继续保留。

MVS 的完整 0000 序列已取得：100 帧 / 300 文件，960×540。官方 10.49GB 原包的
有界流式尝试中断后，经用户明确许可使用 81.67MiB 的解包镜像，全部文件按镜像对象哈希校验，
其中 13 文件另与已取得的官方原文件匹配。详细来源与限制见 reports/data_acquisition_plan.md。
E0 已通过；默认 ORB 有效位姿 23/100，distance1000 诊断配置 31/100，覆盖率仍低。

重现已完成的首轮流程：

    python scripts/run_dataset_e0.py --config configs/datasets/mvs_synth.yaml
    python scripts/run_dataset_orb.py --config configs/datasets/mvs_synth.yaml
    python scripts/summarize_public_experiments.py

E0_MVS/E1A_MVS 保存独立结果目录。MVS 外参 det=-1，必须先统一反射世界 Z，
再对反射已移除的近正交矩阵进行严格有界的数值修正；相机中心和原始矩阵均保留。
未提供采集 FPS，时间字段明确使用 frame_index，不猜成秒数。深度不进入 RGB-only 推理。
OpenEXR 由项目 Conda 变量和脚本启动入口显式启用。

OmniWorld-Game 依据官方 split_info、WXYZ world-to-camera、16bit 深度与 GDINO
动态掩码格式读取。所有输出标记 POSE_PROVENANCE = ESTIMATED_REFERENCE，
使用 normalized_reference_trajectory 文件名。它的 Metric Scale 也不能证明位姿是独立引擎真值。
已取得官方 c5e5ed9a4462 的完整 132 帧 split_0，E0 与无掩码/数据集掩码两组均已运行。
默认 A/B 有效位姿 7/4，对照配置 21/15；未证明过滤改进精度。调用示例：

    python scripts/run_dataset_e0.py --config configs/datasets/omniworld_game.yaml
    python scripts/run_dataset_orb.py --config configs/datasets/omniworld_game.yaml
    python scripts/run_dataset_orb.py --config configs/datasets/omniworld_game.yaml --mask-source dataset
    python scripts/run_dataset_orb.py --config configs/datasets/mvs_synth.yaml --experiment-config configs/experiments/orb_essential_distance1000.yaml
    python scripts/run_dataset_orb.py --config configs/datasets/omniworld_game.yaml --experiment-config configs/experiments/orb_essential_distance1000.yaml
    python scripts/run_dataset_orb.py --config configs/datasets/omniworld_game.yaml --experiment-config configs/experiments/orb_essential_distance1000.yaml --mask-source dataset
    python scripts/analyze_public_ablation.py

共同帧分析默认要求每种配置恰有一个完整 A/B 配对；重复实验后需明确选择固定归档，
不会自动挑最小 ATE。全部 132 帧始终计入覆盖率，未成功帧保持 NaN。
请求的 Mask 不存在时会失败，不静默当成无掩码运行。各数据集的指标表分别保存，
不合并计算跨数据集 ATE。完整研究报告见 reports/dataset_comparison.md 与各数据集报告。
此前 WildWorld 阶段报告保存在 docs/history/wildworld_phase1_reports/。

## WildWorld: retained data path and E0

访问申请已提交，等待 https://huggingface.co/datasets/AlayaLab/WildWorld 作者批准；
获批后再完成本地认证并取得小样本。
具体小样本 ID、逐文件字节数、许可证与访问状态见
reports/data_acquisition_plan.md。默认不下载任何数据或权重。

将 configs/dataset.yaml 的 roots 设置为本地数据目录，例如：

    roots:
      - D:/aaa/GameCam-VO/data/WildWorld/data_part1

每条序列的必需文件是 rgb.mp4 和 state.csv。骨骼投影审查还需 skeleton.npz。
默认最多 10 条，每条只解码起始 15 秒；不自动生成场景标签。

    python scripts/run_e0.py

每次保存到 results/E0/<UTC运行时间>_e0/。根目录 manifest/inspection/validation
为最新视图，归档不覆盖。无数据或未验证时退出码为 2，不能视为实验通过。
独立入口也可使用 inspect_dataset.py 与 validate_camera_pose.py。

相机格式来自官方 README 与投影代码：输入位置为世界相机中心，旋转为 XYZW
OpenGL camera-to-world。本工程输出 T_wc，右/下/前 OpenCV 相机轴，保留原生
世界坐标。变换为 R_wc_cv = R_wc_gl diag(1,-1,-1)，相机中心不变。
没有把长度单位猜成米；meters_per_dataset_unit 只记录证据，不自动缩放数据。

未得到真实证据前，以下配置保持未确认：

- 世界轴方向/手性、原生长度单位与畸变依据；
- 时间戳列、单位与时钟偏移，或独立审查后的帧映射；
- 投影与 RGB 的坐标/同步审查。

不得为通过准入而随意把 confirmed 字段改成 true。需要保留审查图像和来源。
当没有时间戳时，frame_index/FPS 只是候选时间，还必须与实际 PTS 一致，
并具有独立映射证据。禁止把第 N 行默认当成第 N 帧的可信同步。

有数据但未通过的规范化 CSV 标注 CANDIDATE，metadata 的 e0_passed=false；
不能用于可信评价。没有数据时不生成轨迹图、规范化真值或伪测量。
异常值和缺失行保留。输入使用有界 head/tail SHA256 与文件大小/时间指纹，
明确不冒充全文件哈希；派生真值与关联表另保存完整 SHA256。

## E1-A

只允许对同配置、同原始输入且通过 E0 的归档运行：

    python scripts/run_orb_essential.py --e0-run D:/aaa/GameCam-VO/results/E0/<运行目录>

ORB 参数、Lowe 比例、RANSAC、抽样和分辨率均在 YAML 中。逐帧 K 先按实际
resize 缩放，再对各帧特征分别归一化，支持输入焦距变化。recoverPose 的
C_previous→C_current 变换取逆后积分进 T_wc，方向由已知位姿单元测试验证。

单目 essential 平移只有方向；每条边使用单位范数，不能代表真实等距离运动。
纯旋转/低视差、匹配不足与三角化失败记为失败，未填成成功的静止相机。
失败帧以 NaN 轨迹行及原因保留，后续尝试匹配上次成功定位的参考帧。

输出独立运行目录，含 TUM TXT、CSV、特征匹配图、状态日志、运行配置、
轨迹图、指标和源代码指纹。TUM 中失败行含 NaN，读取时不能隐式丢掉。
ORB-SLAM3 官方发布版在现有 Ubuntu WSL 独立构建，说明与全部偏差记录见
baselines/orb_slam3/PATCHES.md，实际运行状态见 reports/omniworld_baseline.md。
MonST3R 只完成前置检查，2.28GB 主权重未下载；见 reports/monst3r_preflight.md。

WSL 构建依赖：cmake、pkg-config、libeigen3-dev、libopencv-dev、libglew-dev、
libgl1-mesa-dev、libegl1-mesa-dev、libx11-dev、libboost-serialization-dev、libssl-dev。
官方源码和 Pangolin 版本固定在 PATCHES.md，下载目录、编译产物和真实原数据不进入 Git。

    wsl -d Ubuntu --exec bash /mnt/d/aaa/GameCam-VO/scripts/build_orbslam3_wsl.sh
    python scripts/prepare_orbslam3_omni.py
    python scripts/run_orbslam3_omni.py

上面的 Python 命令在 gamecam-vo 环境运行。每次原生运行产生新目录，日志与失败不覆盖。

## Evaluation and provenance

evaluate_trajectory.py 要求可信 GT metadata。统一采样序列按显式时间戳
一对一关联，不插值。分别报告 SE(3) 与 Sim(3) 的 ATE、RPE、RotErr、
TransErr（RPE 平移 RMSE）、有效帧数、失败率和 RPE 对覆盖率。
初始化原点计入 pose coverage，运动对成功率另列，分母含全部期望对。
没有可靠尺度时，SE(3) 仅作诊断；Sim(3) 不是米制精度。对齐退化时指标
留空并记录原因。RPE 不通过删去失败帧来重定义相邻关系。

    python scripts/summarize_project.py

只汇总 results 中实际运行记录；比较表没有实测数据时仅保留表头。
NOT RUN 状态单列，M1/M2/M3 尚未得到足够证据作论文结论。

tests/ 使用显式合成的已知位姿、时钟、纹理空白视频测试方向、同步、尺度、
失败覆盖率及准入。合成文件只在 tests/_artifacts/，不进入真实结果表。
logs/ 保留失败尝试及最终测试记录，latest_tests.json 指向最后一次验证。
轨迹诊断图的证据/单位/导出规则见 docs/figure_contract.md。
