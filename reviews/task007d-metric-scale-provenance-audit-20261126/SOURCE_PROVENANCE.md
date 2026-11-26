# 官方来源与证据层级

2026-11-26读取；原始公开网页/API工作缓存仅保留本地。公开包提供身份、链接、源码和结论，
不重复分发全文论文、完整原始数据集或带访问参数的图片URL。

| ID | 来源及固定位置 | 类型 | 能支持什么、不能支持什么 |
|---|---|---|---|
| GH1 | [完整GitHub历史起点](https://github.com/yangzhou24/OmniWorld/tree/bd91509e0b840f3082848cd561da60a695e6b70b)；26个可达提交与文件列表已保存 | 实际源码历史 | 可界定公开实现；不能证明私有生产流程不存在 |
| GH2 | [新增Metric Scale读取和应用](https://github.com/yangzhou24/OmniWorld/commit/79c4819ae13c4c133a64cb6fc3e17bb0d2b584dd) | 2026-03-21代码变更 | CSV消费者、深度和C2W缩放；没有给出因子生成器 |
| GH3 | [调用示例](https://github.com/yangzhou24/OmniWorld/commit/924b99d08fb5011a7dfb28c88b479eba9b25ab2a)、[跟进说明](https://github.com/yangzhou24/OmniWorld/commit/cbfa8819537f738ec1f1dfc26aecfaf305eed5ea) | 文档变更 | 官方米制使用声明；不是独立精度测量 |
| GH4 | [当前Reader](https://github.com/yangzhou24/OmniWorld/blob/bd91509e0b840f3082848cd561da60a695e6b70b/scripts/utils.py) | 实际源码 | 精确解码和乘法位置；不计算或校准s |
| HF1 | [CSV文件历史](https://huggingface.co/datasets/InternRobotics/OmniWorld/commits/main/metadata/omniworld_game_metadata.csv) | 官方版本索引 | 解析6个版本；当前快照/时间戳/身份另存，链接未来可更新 |
| HF2 | [新增尺度列的固定提交](https://huggingface.co/datasets/InternRobotics/OmniWorld/commit/a3934526f95d4e6be043868a08ee4cdac4eacfee) | 2026-03-21 09:17:44 UTC发布 | 一次CSV上传；可见提交消息不含生成方法 |
| HF3 | [发布CSV](https://huggingface.co/datasets/InternRobotics/OmniWorld/blob/a3934526f95d4e6be043868a08ee4cdac4eacfee/metadata/omniworld_game_metadata.csv)、[直接父版CSV](https://huggingface.co/datasets/InternRobotics/OmniWorld/blob/fbeaee2e6d7fff4d7fc09fc6b512c9e60d6d3c64/metadata/omniworld_game_metadata.csv) | 原始字段/字节比较 | 新增列、484行其他字段未变；不能推算生成器 |
| HF4 | [正式发布说明](https://huggingface.co/datasets/InternRobotics/OmniWorld/blob/d6b9b9ff43cb7893504a3471d2b89eac26b4222a/README.md) | 官方声明及读入示例 | 声明物理单位为米；未给出目标UID的独立标定误差 |
| A1 | [非米制早期说明](https://github.com/yangzhou24/OmniWorld/issues/3#issuecomment-3322227112) | 作者2025-09-23解释 | 描述早期相对数据；不能推翻后续发布 |
| A2 | [0.004解释](https://github.com/yangzhou24/OmniWorld/issues/3#issuecomment-3494867729) | 作者2025-11-06解释 | 数值缩放与线性化；不是米换算常量 |
| A3 | [Game与其他子集来源区别](https://github.com/yangzhou24/OmniWorld/issues/10#issuecomment-3568742850) | 作者2025-11-24解释 | ReShade原始Game depth来源；不证明后来尺度因子独立 |
| A4 | [MoGe-2近似方案](https://github.com/yangzhou24/OmniWorld/issues/10#issuecomment-3570627221) | 作者2025-11-24建议 | 存在采样帧中位比值方案；不是当前CSV生产收据 |
| A5 | [CSV位置答复](https://github.com/yangzhou24/OmniWorld/issues/20#issuecomment-4127257933) | 作者2026-03-25答复 | 只给文件位置，不补齐生成机制 |
| A6 | [相机来源说明](https://github.com/yangzhou24/OmniWorld/issues/23#issuecomment-5384909434) | 作者2026-08-23答复 | 相机是估计/优化结果；不能充当独立引擎运动标尺 |
| P1 | [OmniWorld arXiv2509.12201v2](https://arxiv.org/html/2509.12201v2) | 正文与附录 | 读了2.1/2.2/3.1/C.1/D；此版本早于2026年尺度发布 |
| P2 | [OpenReview接收版入口](https://openreview.net/forum?id=1y1YFKb9pp) | 后续材料访问受限 | 没有独立读到全文/附件，不能用于否定或认证新尺度 |

当前HF revision：`4e34897a2fcf8e1cc44b1ae8d2bbd0188c8f2841`。
其CSV Git Blob为 `00b580ead4422f315800191127cf749b38eff697`；
SHA256为 `460ad6d26f775b265da462be679fa96bff6df4e4211a66a9b2aa7d303a826fdf`。
与2026-03-21上传内容、已有本地66,930字节文件完全一致。

全部源码SHA/Git Blob、历史CSV身份和作者身份/日期/解释见evidence目录。
作者为OWNER的10条相关公开解释已逐项核实；其他用户的质疑不当作本轮独立测量结果。
没有联系作者或执行任何讨论内的代码。
