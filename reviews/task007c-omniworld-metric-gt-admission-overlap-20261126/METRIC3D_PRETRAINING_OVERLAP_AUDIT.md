# Metric3D 训练重叠证据分级

| 判断 | 等级 | 固定来源 |
|---|---|---|
| Virtual_KITTI 在公开 ViT-Large 活跃训练列表 | CONFIRMED_SOURCE | `sources/metric3d/vit.raft5.large.py:24,75,810`；不是只在注释中出现 |
| VKITTI 配置的训练注释路径 | CONFIRMED_SOURCE | `sources/metric3d/vkitti.py:16`；`public_datasets.py:370-377`有数据登记 |
| 本项目实际 Metric3D 权重的精确 VKITTI2.0.3 帧清单 | UNVERIFIED | 公开训练说明称私有训练注释JSON未提供；公开重实现不等于权重逐帧训练记录 |
| OmniWorld-Game 名称未出现在本轮检查的公开训练配置 | LIMITED_NEGATIVE_EVIDENCE | 不能由名称缺失证明所有私有训练、DINO预训练和网络图像均无重叠 |
| OWG Game 原始 render depth 不是 Metric3D 的预测输出 | SUPPORTED_BY_AUTHOR_PIPELINE | ReShade渲染缓冲区来源；与其他OWG子集的估计pipeline区分 |
| 这3个UID的米制缩放来源独立、精确 | UNVERIFIED | CSV数值与使用方法已核实，因子生成/物理锚点仍缺 |

Metric3D固定提交：`eb5b6fac0dc155e4e52f576e304fbf11655ff339`。
对应历史R2.1权重SHA256：`15328ffc42b528b95f188687418f6f03b3f123eb34ccdbd686c112abbea6d972`；本轮未加载。
7份来源文件的Git Blob与SHA验证在 `evidence/SOURCE_BLOB_VERIFICATION.json`。

结论：VKITTI2不得标为训练未见独立测试；OWG也暂不能获得“预训练完全无重叠”的证书。
UID不跨Calibration/Dev/Evaluation解决本项目内部泄漏，不能解决基础模型训练数据未知问题。

来源：[Metric3D训练配置](https://github.com/YvanYin/Metric3D/blob/eb5b6fac0dc155e4e52f576e304fbf11655ff339/training/mono/configs/RAFTDecoder/vit.raft5.large.py)、
[公开训练说明](https://github.com/YvanYin/Metric3D/blob/eb5b6fac0dc155e4e52f576e304fbf11655ff339/training/README.md)。
