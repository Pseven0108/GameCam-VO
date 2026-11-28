# 实现与独立性审计

候选实现位于candidate/native/droid_kernels.cu的robust_prior_terms_cuda和BA itr循环。
所有16个原生__global__ kernel正文与既有A5候选逐字一致；BA的C/b装配有预期修改，
不得将build记录中的kernel_arithmetic_changed=False误读为“BA公式完全未改”。
原安装扩展没有被替换。以独立名称local_mpsfm_robust_c3414af6编译。
correlation/altcorr只做PyTorch dispatch API的type→scalar_type兼容替换。

robust_controller.py限定MAIN、非motion-only、metric prior开启的调用。
未知或缺失阶段停止；初始化、Final BA、Filler均直通原版。
REAL_STATE_IRLS_ORACLE.json和FIRST_ROBUST_NATIVE_STATE.npz提供逐元素核查。
完整原生两轮迭代保留；没有将两轮拆成独立调用。

A5的coefficient_map来自原TASK011B ValidityAwareMax，使用同一深度、Flip和confidence缓存。
A5作用于深度先验，不将其描述为UBA几何权重。q与a相乘只用于先验项；阻尼始终(1-ma)eta。
没有Scale/Shift、物体mask或GT回流。GT fixture只被离线评分器读取。

端点证据仅涵盖一个真实状态的容差验证，原生U atomic累加仍可能数值波动；
不宣称整个系统逐位确定或与远端正式环境等价。
