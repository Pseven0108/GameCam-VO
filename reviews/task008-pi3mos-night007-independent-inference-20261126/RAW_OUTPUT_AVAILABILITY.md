# 原始数组与公开Review范围

完整运行目录（服务器）：`/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R2_FORMAT_VERIFIED`。
完整取回目录（本机）：`D:/aaa/GameCam-VO/experiments/task008_pi3mos/retrieved`。
原始浮点数组：`outputs/night007/A/predictions/00301.npz` 至 `00332.npz`，B同名，共64份，821,090,264 bytes。
原始RGB复制与上下文仍在本机/服务器；输入对应表和SHA见evidence/INPUT_IDENTITY_BEFORE.json、INFERENCE_INPUT_OUTPUT_MANIFEST.json。独立校验的520项清单见evidence/RESULT_COLLECTION_MANIFEST.json。

为遵守“不提交模型权重和大型预测文件”和仓库数据边界，公开包不包含NPZ、原始RGB、权重、环境二进制或源码clone。全量浮点预测没有删除或重编码。
公开包保留全部64张Overlay、64张原图网格二值Mask、每帧概率灰度/热力显示、Confidence/辅助深度、完整联系表、所有推理/分析代码、配置、运行/部署日志和身份清单。概率显示为8bit派生图，不替代float32概率。
部分公开显示图缩为640×360以便浏览：Overlay/概率热力用LANCZOS，概率灰度用BILINEAR；Mask不重采样，Confidence/深度保留原生672×378。VISUAL_DELIVERY_MANIFEST.csv逐项列出原/派生SHA与处理方式。
