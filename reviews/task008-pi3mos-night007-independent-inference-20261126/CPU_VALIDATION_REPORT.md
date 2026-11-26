# CPU合成与真实产物复核

- 合成颜色/像素域/尺寸/逆映射检查通过，与官方独立RGB reader逐位一致，未初始化CUDA。
- 64份真实NPZ的ID、上下文、SHA、shape/dtype、有限性、概率范围、正深度与local_points z、源RGB复制身份均通过。
- 64份原图概率的独立float64半像素插值最大差2.64760107e-06（预设容差5e-5）；所有二值Mask逐像素等于保存概率>0.4。
- 0.2/0.4/0.6面积及Confidence均值从数组重新计算，与运行统计一致。
- 520份传输文件SHA全部通过；52张源图与1830份既有DROID源码/配置/JSON前后SHA一致。

这些是产物、数学坐标与资产保护合同验证，**不是64个独立场景，也不是动态检测准确性测试**。审计脚本不导入Torch，不运行模型或GPU；详细逐帧结果见statistics/SAVED_PREDICTION_AUDIT.csv。
