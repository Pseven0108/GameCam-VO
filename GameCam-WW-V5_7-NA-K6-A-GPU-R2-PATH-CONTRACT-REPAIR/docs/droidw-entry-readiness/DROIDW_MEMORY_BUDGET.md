# DROID-W 显存预算

结论：固定缓存可计算，完整峰值尚不能证明。GPU为RTX2080Ti、22528MiB，开始时空闲约22002MiB。GPU_ADMISSION_ANALYSIS.json保留不确定项。

保持buffer350、512×288、warmup12、stride1、motion_filter3.0、mapping=false、uncertainty384。逐个解析原生DepthVideo构造器张量得到GPU固定缓存2231.01MiB，CPU固定缓存959.77MiB，明细在DEPTHVIDEO_STATIC_MEMORY.json。该和不包括后续关键帧图、相关性体、BA、深度/特征先验中间激活或CUDA库工作区。四份checkpoint文件大小只能作为存储量参考，不能等同权重/激活的完整显存预算。

历史同GPU运行最高NVML used为715.69MiB；CUDA Allocated为0。主checkpoint在CPU读入后就被Arena边界拦截，未达到完整Tracker/先验运行，不能外推为完整初始化峰值。

本轮小型CUDA合成峰值allocated 8.17MiB、reserved 22.00MiB，只证明这些小算子工作。当前没有证据判定22GiB不足，也没有完整上界证明它足够。准入矩阵把完整显存预算列为UNVERIFIED，最终PARTIAL_PASS。不得因此降低buffer/图像分辨率/帧数或512MiB保护。
