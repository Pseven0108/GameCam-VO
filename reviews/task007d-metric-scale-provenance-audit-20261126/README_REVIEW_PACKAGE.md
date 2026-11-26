# 评审包阅读顺序与范围

先读FINAL_REVIEW、SCALE_GENERATION_ANALYSIS和GT_ADMISSION_DECISION，再读UID_SCALE_AUDIT.csv与evidence。
SOURCE_PROVENANCE给出官方固定版本与来源层次；NEXT_STAGE_RECOMMENDATION列出未闭合的最小证据需求。

包含：本轮全部报告、分析代码、源码快照/历史补丁、身份核验、元数据版本对比、作者说明释义、CPU数学演示和状态入口副本。
不包含：本地sources_work里的完整网页、全文论文、历史整份原始CSV或评论正文；也不包含原始RGB/Depth、模型权重、环境二进制或凭据。
这些本地工作输入保持不变；公开包保存其URL/版本/hash和必要的派生审查记录。
原始数据/全文来源不随Review再分发，不影响本轮报告与证据的完整交付。

`code/audit_evidence.py`消费本地固定工作缓存进行身份与范围核验；不是下载数据或运行模型的入口。
复核来源时应按记录URL取得相同版本并核对hash，不能把当前main自动替换成历史证据。
`sources/official`中的下载脚本只是被审计的官方源码，未执行，不应因随包存在就启动全量下载。

没有新的模型准确性结果；141项历史hash和6份源码身份通过，不代表141个实验样本或物理GT通过。
