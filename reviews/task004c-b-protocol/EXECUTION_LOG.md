# Task004C-B 本轮执行记录

日期：2026-11-24（Asia/Shanghai）。独立目录：D:/aaa/GameCam-VO/experiments/DROID_W_TASK004C_B_PROTOCOL_20261123T170327098Z。

1. 分段读取用户534行授权附件；仅允许协议设计/只读审计，不允许四臂GPU运行或自动487帧采集。检查项目祖先AGENTS.md，未发现额外指令内容。此前读取的复现skill不适用于本次开放协议设计，未执行其复现/训练流程。
2. 读取历史Task004C报告、初始化差异、原生调用manifest、源码副本；未解压原始RGB、未读取新GT、未连接SSH。
3. 本地辅助Git查询实际返回项目父仓库HEAD；未把它当baseline。初次5个git-show读取未成功，原始错误保存在SOURCE_LOOKUP_LIMITATIONS.json；未保存退出码的部分明确为null。后改为官方保存tree Blob和历史冻结SHA，8份补充源码均一致。
4. 新建独立目录，只复制所需源码和证据、生成规范。没有改原始R2、冻结源码、权重、扩展、历史结果或其他实验目录。
5. 使用现有C:\ProgramData\miniconda3\python.exe，CUDA_VISIBLE_DEVICES为空，执行tools/audit_protocol_inputs.py。仅标准库、ast解析、CSV/JSON和ZIP中央目录读取。处理18份Python证据、303处属性写入位置、24份历史归档和24行历史运行记录；stdout/stderr与退出码0保存在logs/INPUT_AUDIT.*。未导入模型或PyTorch。
6. 设计唯一INIT_D0 C0和47个tensor/族条目；记录完整恢复、实际子进程RNG、alias和尾块条件。设计两份Schedule JSON Schema和四臂顺序B1/B4/B2/B3；未生成可执行C0或真实Schedule。
7. 核算视频tensor逻辑值7,468,230,540 bytes；最后历史data free14,257,266,688 bytes。保守四raw+四ZIP为9,560,857,988 bytes，另加C0、调度、临时空间；不凭旧52GiB或压缩率通过门槛。
8. 已生成要求的10份文件、阅读说明、证据、只读核算工具与安全记录。随后只进行交付一致性与ZIP核验；其真实stdout/stderr/退出码和结果附后保存。

本轮新增：GPU运行0、BA调用0、C0采集0、自然Schedule0、四臂0/4、SSH连接0、CUDA初始化0、研究模型导入0、自动重试0。没有重启/关闭/释放实例，也没有清理任何历史文件。

本轮验证只限文档/JSON/schema/身份及打包，不作为研究CPU实验、原生恢复测试或GPU证据。

## 实际交付检查

- 完成时间（Asia/Shanghai）：2026-11-24 01:40:46。
- tools/validate_delivery.py 实际运行退出码0，14项本地交付静态检查通过，0项失败；stdout/stderr/收据见 logs/DELIVERY_VALIDATION.*。它们不是研究实验或原生恢复测试。
- 两份Schedule schema逐类补齐22种事件payload必填项；修改仅限本轮协议设计文件，见 evidence/SCHEMA_DELIVERY_REVIEW.json。
- 现有Python没有jsonschema包；未安装依赖。使用标准库检查JSON解析、选定schema语法、内部引用和字段闭包；没有声称已做完整Draft2020-12元schema认证。
- 22份原始输入的SHA256、大小和mtime（跨API精度容差0.01ms）全部保持一致，见 evidence/PROTECTED_INPUTS_AFTER.json。
- 本次恢复后的首次Node工具能力检查因process不可用，在启动Python之前报错；改用显式CPU环境后检查退出码0，未启动任何研究计算。
- 最终SHA清单和ZIP校验由独立打包工具完成，真实输出保存在 artifacts，避免修改包内文件导致自失效。

已将历史保存的官方Git tree原文附入 evidence/OFFICIAL_FROZEN_GIT_TREE.json（255项、77,628 bytes），绑定原始路径与SHA256；没有重新访问网络。最终静态核对同时检查8份补充文件与该树相符。
