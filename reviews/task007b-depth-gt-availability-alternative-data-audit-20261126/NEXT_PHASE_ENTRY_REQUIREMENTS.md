# 下一阶段准入条件与停止边界

本轮完成数据源审查，不自动执行下载、推理、校准或训练。

推荐优先审查Virtual KITTI 2的Calibration-only 12对样本获取方案：Scene01/02×clone/fog/morning/overcast/rain/sunset，各取第一个经元数据验证的共同frame ID。
每对需同一Camera_0的RGB、depth、class及K/extrinsic记录。当前没有实际成员索引，不能假称文件已经取得或身份已认证。

先决条件：

1. 固定官方2.0.3 URL、HEAD身份和MD5来源；对按成员传输明确其证据弱于整包MD5核验，不能声称整包已PASS。
2. 先核算索引/传输实际字节，建议下一阶段从256MiB硬预算的小样本方案开始；当前不是下载批准。若必须下载14.62GiB以上整包，单独提交准确方案。
3. PNG保持uint16；由官方厘米Z-depth转米；报告0/65535、Sky/Undefined及其他异常，不自动补零或插值GT。
4. 核对RGB/depth/class/K同frame、同camera、同分辨率与像素中心；保存原文件，不修补原始数据。
5. 核对Metric3D输入K、canonical变换及恢复尺度；使用原始冻结模型，不能把输入适配差异写成Confidence改善。
6. Calibration/Development/Evaluation按母Scene分离，验证重复身份；不得用Evaluation拟合参数、mask、先验floor或错误阈值。
7. 样本GT准入完成后才单独启动小批量Metric3D推理；本轮GPU授权为无，不消耗任何GPU运行。

若继续VIPER像素校准，必须先提供确切官方GT产品及单位/有效性规范；排行榜或PFM提交接口不足以满足该条件。
Scalix训练、CADP/BA接入及VIPER全量测试继续暂缓。
