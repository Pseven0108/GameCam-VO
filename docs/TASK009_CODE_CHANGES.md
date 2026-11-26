# TASK009 代码、环境和复现说明

新增代码在 `gamecam/modules/dynamic_prior`、`gamecam/modules/motion_decomposition`、`gamecam/compat`；运行/评价/可视化/证据收集脚本与23项CPU测试在 `experiments/TASK009`。
统一配置位于 `configs/task009/local_exploration.json`。归档内 `code/` 是交付时自有代码快照。
原工作区6份用户dirty文件SHA全部保持；详情见保护收据。没有执行reset、clean或stash，没有连接远端。

## 候选上游差异

外部DROID-W候选只变更构建sm120、ATen `.scalar_type()`分派和未使用DepthAnythingV2的延迟导入。
LieTorch的ATen兼容、构建路径和仅核心扩展的构建变更单独以完整patch公开；未替换原生产二进制。
`src/lib/droid_kernels.cu` BA求解公式不变。单纯编译成功不代表跨环境数值等价。
两个算法hook完全在自有代码中运行，不复制第三方后端。

## 实际环境与依赖

Windows现有Conda迁到 `D:\aaa\envs\gamecam-vo`，Python3.11.18、torch2.15.0+cu132/torchvision0.29.2+cu132。
新加独立模型所需omegaconf/einops/timm/evo/roma/scikit-image/scikit-learn等；安装前后快照在证据目录，pip check通过。
DROID原生运行库单独在D盘 `runtime/wsl310`（torch2.7.1+cu128）及 `runtime/cuda128`；Python3.10.18。
本地驱动与其他Conda环境没有改动。代码、运行库、环境、缓存、临时文件和结果均写D；Windows/WSL发行版根盘/驱动/分页文件未整体迁移。
环境与缓存共107416文件两端SHA核验；evo配置另2文件核验；C旧路径通过Junction兼容。

## 重跑命令

以下命令会新建输出，**本轮交付后没有自动再执行**。需先按来源收据恢复外部repo、权重与本地RGB/先验；公开ZIP不含这些资产。
路径对应本机独立worktree，换机器须修改run_native.sh与运行器显式输入根；不要用旧结果目录作为新输出。

```powershell
# CPU合同检查，不启动模型
Set-Location D:\aaa\GameCam-VO-TASK009
& D:\aaa\envs\gamecam-vo\python.exe -m unittest discover -s experiments/TASK009/tests -v

# E0 / E1 / E2 / E3，用全新的输出目录
wsl -d Ubuntu -- bash /mnt/d/aaa/GameCam-VO-TASK009/experiments/TASK009/scripts/run_native.sh experiments/TASK009/scripts/run_droid_window.py --priors experiments/TASK009/outputs/native_priors_216x384_r3 --output experiments/TASK009/outputs/NEW_E0
wsl -d Ubuntu -- bash /mnt/d/aaa/GameCam-VO-TASK009/experiments/TASK009/scripts/run_native.sh experiments/TASK009/scripts/run_droid_window.py --priors experiments/TASK009/outputs/native_priors_216x384_r3 --gate --output experiments/TASK009/outputs/NEW_E1
wsl -d Ubuntu -- bash /mnt/d/aaa/GameCam-VO-TASK009/experiments/TASK009/scripts/run_native.sh experiments/TASK009/scripts/run_droid_window.py --priors experiments/TASK009/outputs/native_priors_216x384_r3 --static-tracks experiments/TASK009/outputs/mdtracker_metric_32f_160x280_fp32_r1 --output experiments/TASK009/outputs/NEW_E2
wsl -d Ubuntu -- bash /mnt/d/aaa/GameCam-VO-TASK009/experiments/TASK009/scripts/run_native.sh experiments/TASK009/scripts/run_droid_window.py --priors experiments/TASK009/outputs/native_priors_216x384_r3 --gate --static-tracks experiments/TASK009/outputs/mdtracker_metric_32f_160x280_fp32_r1 --output experiments/TASK009/outputs/NEW_E3
```

不安装hook即可回到**本地探索E0**，不是宣称复现旧正式R2。原生产分支/冻结扩展始终保留，无需回滚。
独立MDTracker、WildGS、Easi与LEAP入口及其参数均在 `code/experiments/TASK009/scripts`；对应实际配置保存在statistics/receipt。

## 公开交付边界

公开：自有代码、候选patch、配置、9组完整小型轨迹/关键帧/BA观测/日志、独立模型小型预测、评价/派生可视化、来源/保护/迁移收据。
不公开：权重、安装环境、二进制扩展、原始RGB、原始GT、32份大先验数组、107416文件的完整本机迁移清单以及包含临时下载链接的日志。
省略物的路径/大小/SHA写入 `LOCAL_ONLY_ARTIFACTS.csv`，不是伪称公开包含全部本地文件。
早期运行未在receipt写自有source SHA，保存的初版runner/静态adapter及后续同输入逐位核验作为补充；不追写旧receipt、不伪称每次都有完整提交身份。
