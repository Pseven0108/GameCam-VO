# 当前状态 · 2026-11-24

## 当前研究主线

- 项目：GameCam-VO；主数据集：VIPER。
- 主Baseline：DROID-W。原版DROID-SLAM只作为既有对照，不在本次发布中重跑。
- stride=1；stride=4分支已放弃作为当前主线。
- 当前候选：668a88c74c7f7a88a572679d2bd8e86c0a05514b。
- 当前阶段：TASK004C-B-NATIVE-RELEASE-FIXES，STOPPED_FOR_USER_REVIEW。

## 本轮已验证

1. Local BA缺失/错误phase、motion_only均失败关闭，保留原vanilla安全边界与INIT_D=0。
2. buffer保持500。原尺寸CPU文件映射共享读写通过，新增34项与历史118项完整回归152/152。
3. 精确序列化逻辑字节预算机制通过合成测试；每次实际写入前重新检查空间。
4. 原始093完整候选、R2配置、权重、CUDA扩展与BA数学未修改。

## 尚未验证或未授权

- 真实Tracker/Rerun GPU跨进程链路未验证。
- 完整真实C0大小未知，保留多个arena的后续全流程存储尚未准入。
- 本轮没有真实C0、RGB前缀或B1/B2/B3/B4。
- 不能把合成通过解释为真实SLAM性能提升。

GitHub发布是文档和源码同步，不包含任何新的实验运行授权。所有历史执行记录见各阶段原报告。
