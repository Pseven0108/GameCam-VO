# 原始来源与证据分级

- 官方 Metric3D 固定代码：https://github.com/YvanYin/Metric3D/tree/eb5b6fac0dc155e4e52f576e304fbf11655ff339
- DROID-W 目标：https://github.com/MoyangLi00/DROID-W/tree/c3414af6047d06bafc1a6645d09f23247f3b2cdc
- Metric3D v2：https://arxiv.org/abs/2404.15506
- GrUMoDepth：https://arxiv.org/abs/2208.02005 ，https://github.com/jhornauer/GrUMoDepth
- UfM：https://lean.mit.edu/papers/ufm-icra ，https://github.com/mit-lean/ufm
- DepthCov：https://arxiv.org/abs/2303.12157 ，https://github.com/edexheim/DepthCov
- MVS-Synth：https://phuang17.github.io/DeepMVS/mvs-synth.html

OBSERVED：实际文件哈希、CPU测试与GT审计。SOURCE_DERIVED：score含义、mask、256 bins。
AUTHOR_REPORTED：论文数据集和效果。HYPOTHESIS：严重错误可能缺乏低confidence监督。
UNVERIFIED：模型实际数值分布、真实误差预测力、跨环境表现和runtime。
不将这些级别互换。没有联系作者。
