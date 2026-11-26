# 数据源选择：VIPER主线不变，另建校准候选

**首选候选：Virtual KITTI 2.0.3；当前仅通过文档/元数据可行性，尚未通过实际样本准入。**
不是将其替换为GameCam-VO主数据集，也没有下载新样本或重新运行Metric3D。

| 数据源 | 深度来源与单位 | 主要限制 | 当前定位 |
|---|---|---|---|
| VIPER | 当前无可准入的公开配对像素GT | online test不能用于拟合；GT、单位、mask未建立 | 保留VO主线；像素校准NO-GO |
| MVS-Synth | 已有EXR及内部几何证据，物理单位未知 | 0000/0001已观察；不能给绝对尺度可靠性证书 | 只允许考虑既有数据上的非米制探索性形状诊断 |
| Virtual KITTI 2.0.3 | Unity渲染Z-depth，uint16 PNG，编码值×0.01米 | 天空/远平面mask要明确；只有5个母场景，变体高度相关；没有Night/Snow | 最优先小样本GT准入候选 |
| TartanAir v1 | 仿真NPY深度，文档明确米制 | 天空可为很大的有限值；需核对实际dtype、Z/range及版本；相关昼夜地图不可跨划分 | 次选环境多样性候选，不能直接复用v2约定 |
| NYUv2 | Kinect投影到RGB的rawDepths米制，另有inpainted depths | 真实传感器空洞、边缘/同步误差；室内域与VIPER不同，填补值不等于直接测量 | 后续真实环境传感器有效区域辅助对照 |

没有把“仿真GT”写成“真实传感器GT”。Virtual KITTI 2与TartanAir是渲染监督；NYUv2的rawDepths才是传感器来源且有缺测。
以上数据是否进入原始Metric3D预训练尚未建立，不能据此承诺pretraining-unseen或严格zero-shot泛化。

## Virtual KITTI 2的直接优势与剩余门禁

官方明确深度是到相机平面的Z值、1编码单位为1厘米，提供RGB、深度、K、extrinsic及class颜色表。
这比当前VIPER缺少像素GT、MVS缺少原始物理单位的证据链更完整。
官方flow的无效B通道是flow规则，不能挪作depth mask。
可提议排除编码0、65535饱和和官方语义Sky/Undefined，另报告覆盖率；这是待冻结的评估域规则，不是声称官方已提供同一mask。

HTTP HEAD实测：RGB归档7,532,472,320 bytes，depth归档8,145,715,200 bytes，textgt归档24,451,078 bytes；官方MD5清单已只读取得。
RGB+depth+textgt合计约14.62GiB，尚不含class segmentation。**没有下载这些归档。**
返回Accept-Ranges=bytes只证明服务声明，不证明已实现可靠的按成员小样本提取；未取得TAR成员索引或单帧官方哈希。
下一阶段若无法在事先批准的传输预算内只获取目标成员，必须报告，不自行升级为整包下载。

## 推荐决策

建议下一阶段先审核12个Calibration候选RGB/GT/class/K配对的最小获取方案，仅用Scene01/02，避免提前观察Evaluation场景。
实际文件身份、空间对齐、深度编码和mask通过后，再考虑有监督Confidence实验。具体分组见`CALIBRATION_EVALUATION_SPLIT.json`。
本轮不执行该小样本阶段，不训练预测头、不接入CADP，不改变VIPER正式实验。

来源：[Virtual KITTI 2官方](https://europe.naverlabs.com/proxy-virtual-worlds-vkitti-2/)；[TartanAir v1格式](https://github.com/castacks/tartanair_tools/blob/841584a8a1ebbdcc832430212609d48b6b624443/data_type.md)；[NYUv2官方](https://cs.nyu.edu/~fergus/datasets/nyu_depth_v2.html)。
