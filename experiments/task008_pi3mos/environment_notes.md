# 独立环境与部署记录

仅新建 `/opt/gamecam-pi3mos/envs/pi3mos-infer`，环境位于系统盘。Python3.10，torch2.3.1+cu121，torchvision0.18.1+cu121，NumPy1.26.4，huggingface_hub0.26.5；完整冻结清单见evidence/ENVIRONMENT_PIP_FREEZE.txt。pip check通过。

RTX3090 24GiB，驱动580.119.02。模型/权重/输入结果位于数据盘。没有运行pip install .，没有安装DPVO扩展、下载DPVO权重或编译CUDA。使用原源码的Torch RoPE回退和可选xformers缺失时的原生路径。

远端官方源码checkout超时后，按授权从本地新clone官方仓库再传输；HEAD保持指定commit。远端Torch/CUDA依赖下载实测过慢，两次仅停止本任务自己的未完成pip下载进程，随后在本地下载精确Linux wheel，逐个传输SHA验证并离线安装到新环境。没有改动旧DROID-W或本地gamecam-vo环境。

初始官方权重被本任务命名为.pth，但实际是safetensors。第一次读取失败时前向0次；保存R1现场，单独R2采用safetensors安全读取并strict=True。未修改权重字节、未使用随机初始化代替、未放宽参数键校验。

最终系统盘剩余约0.68GiB、数据盘约3.68GiB。当前实验已完成，所有后续推理输出均写数据盘；下一阶段安装前需重新核验空间。未清理历史资产、未重启、未关机。

GitHub原有授权在新克隆实例仍可用，仓库Public、默认分支及历史Release均保持。token始终留在既有专用wrapper中，不进入报告、源码或归档。
