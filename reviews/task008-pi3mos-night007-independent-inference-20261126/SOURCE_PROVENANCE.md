# 官方源码与独立适配器依据

全部官方文件以固定提交1b81d729c4259a5a775eb4aae41f959eea38ae14的Git blob核验，身份见SOURCE_PROVENANCE.json。

- [Pi3.forward及原生sigmoid输出](https://github.com/PRBonn/Pi3MOS-SLAM/blob/1b81d729c4259a5a775eb4aae41f959eea38ae14/pi3/models/pi3.py)：独立模型、内部ImageNet归一化、dynamic/conf输出、exp正深度。
- [官方独立RGB读取与通用tensor预处理](https://github.com/PRBonn/Pi3MOS-SLAM/blob/1b81d729c4259a5a775eb4aae41f959eea38ae14/pi3/utils/basic.py)：PIL RGB、255000像素、14倍数、LANCZOS与ToTensor。
- [DPVO Pi3权重读取及调用](https://github.com/PRBonn/Pi3MOS-SLAM/blob/1b81d729c4259a5a775eb4aae41f959eea38ae14/dpvo/dpvo.py#L159)：官方支持safetensors加载；本轮不运行DPVO。
- [DPVO图像流](https://github.com/PRBonn/Pi3MOS-SLAM/blob/1b81d729c4259a5a775eb4aae41f959eea38ae14/dpvo/stream.py)：cv2路径需核查通道/数值域；独立适配器使用明确RGB路径。
- [原生阈值0.4](https://github.com/PRBonn/Pi3MOS-SLAM/blob/1b81d729c4259a5a775eb4aae41f959eea38ae14/dpvo/net.py#L110)：只作参考阈值，不是当前数据上调优的阈值。
- [官方安装与权重来源](https://github.com/PRBonn/Pi3MOS-SLAM/blob/1b81d729c4259a5a775eb4aae41f959eea38ae14/README.md)：本轮绕过setup.py和完整SLAM，仅安装独立forward需要的依赖。

本报告的实际行为以运行收据和保存数组为证据，源码推导不冒充GPU结果；定性观察不冒充GT评价。
