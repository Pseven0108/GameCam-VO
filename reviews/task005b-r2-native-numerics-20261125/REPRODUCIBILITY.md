# 重现与输入合同

授权边界只包含D0_S1_RGB233。用户未批准扩展到S0或重新获取序列前缀。

本次运行脚本：01_runtime/replay_r2.py。需Linux、既有Torch2.1.0+cu118、nvcc11.8、Eigen和已固定的原扩展。原扩展不得替换；候选独立构建。

输入以完整storage序列化保存；每个唯一storage只克隆一次，再按原offset/shape/stride恢复view并验证alias等价类。每次调用前恢复封存RNG，torch.set_num_threads(2)，torch.no_grad，内部iterations=2。

完整ZIP的raw/input/snapshot_D0_S1_RGB233.tar包含原封存快照，原tar SHA及每成员SHA见00_intake/INPUT_SNAPSHOT_VERIFIED.json。raw/plain/和raw/trace/含10份NPZ及STARTED/receipt、完整stdout/stderr；diagnostic_binary含本次观测.so。所有数组保留原shape/dtype；原disps不clamp，所有输出均有限。

分析脚本04_analysis/analyze_pairs.py、feedback_math.py、extended_diagnostics.py使用CPU NumPy。feedback_math不反序列化模型；对可信快照gzip+torchZIP的storage直接读字节。

原运行器使用服务器绝对路径。本轮完整包不是重新部署环境的自动安装器；重放必须显式核对环境及输入身份。原二进制来自此前冻结环境，本轮未重新安装依赖或编译原扩展。

数值判定保持abs(a-b)<=1e-6+1e-5*abs(b)。未以本轮观察到的最大重复误差构造新通过阈值；也未用n=2估计具有统计保证的误差包络。
