# 执行记录

1. 读取Task005A原始报告、提案、冻结CUDA源码及Task004C-B封存清单。
2. 第一次SSH使用默认known_hosts，因当前端口条目不存在失败；未接受未知密钥。随后找到历史专用pin文件，验证其ED25519指纹，使用历史HostKeyAlias完成hostname检查及一次只读资源/文件清点。没有修改known_hosts。
3. 可信目标主机与之前实例一致。nvidia-smi两项查询均返回Exec format error；用户确认当前无卡启动。未修改驱动、启停实例或初始化CUDA。
4. 只读C0 TAR目录和manifest JSON，不提取/反序列化Tensor；扫描四组observer/native trace目录和npz成员名。保存12个目标状态元数据，确认目标完整BA输入缺失。
5. 创建独立ba_paths_cuda候选与CPU数学参考，冻结原始源码blob；没有编译新模块或触碰已安装扩展。
6. 首轮38项检查中1项fixture报错，保留日志；修正fixture后38/38通过。逐项测试实录见04_tests。
7. 形成有明确资源规模的定向补采方案，整理公开评审包，验证历史封存与ZIP/文件哈希；GitHub发布另有可核验回执。

真实GPU实验0，模型推理0，完整/前缀RGB执行0，原生BA重放0，远端文件修改0。
