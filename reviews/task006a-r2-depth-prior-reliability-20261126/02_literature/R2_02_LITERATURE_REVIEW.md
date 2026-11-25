# R2-2 文献与适用边界

阅读的是与本任务有关的 Method、Experiments 和 limitations/conclusion；下述论文结果均是作者报告，
不是 GameCam-VO 的复现实验。访问路径及全文读取范围见 PAPER_READING_LOG.json。

## Metric3D v2

Mu Hu, Wei Yin, Chi Zhang, Zhipeng Cai, Xiaoxiao Long, Kaixuan Wang, Hao Chen, Gang Yu, Chunhua Shen,
Shaojie Shen. *Metric3D v2: A Versatile Monocular Geometric Foundation Model for Zero-shot Metric Depth and Surface Normal Estimation*.
IEEE TPAMI 46(12), 10579–10596, 2024；DOI 10.1109/TPAMI.2024.3444912。arXiv v4 日期是 2025，不能把它当期刊年份。
[论文](https://arxiv.org/abs/2404.15506)；[官方代码](https://github.com/YvanYin/Metric3D)。
Canonical camera transformation 配合联合 depth-normal 迭代预测，提供跨相机的零样本几何估计。
其跨数据集 depth/normal benchmark 支持研究动机，未提供本项目 VIPER confidence 的误差识别或概率校准证书。
本轮还追踪了实际 ViT Large decoder 和 confidence supervision；init-bin 分布与最终 confidence 是不同信号。

## GrUMoDepth

Julia Hornauer, Vasileios Belagiannis. *Gradient-based Uncertainty for Monocular Depth Estimation*. ECCV 2022。
[论文](https://arxiv.org/abs/2208.02005)；[官方代码](https://github.com/jhornauer/GrUMoDepth)。
利用原图与扰动图预测的辅助差异反向传播，读取 decoder 特征梯度并进行通道归约；固定预训练模型即可做后处理，
不需要重新训练深度模型。其范式约需两次 forward 和一次 backward，成本和梯度层选择依赖网络。
作者在 Monodepth2、KITTI/NYU 等设置研究 uncertainty ranking；不能把其结果直接转移到 Metric3D/VIPER。
Metric3D inference 的 no_grad 入口和八轮 RAFT 会增加迁移工作；应在 A/B/C 证据不足后才花费该成本。

## Uncertainty from Motion (UfM)

Soumya Sudhakar, Vivienne Sze, Sertac Karaman. *Uncertainty from Motion for DNN Monocular Depth Estimation*. ICRA 2022，
DOI 10.1109/ICRA46639.2022.9812222。
[作者论文页](https://lean.mit.edu/papers/ufm-icra)；[官方代码](https://github.com/mit-lean/ufm)。
原 PDF 主站 TLS 超时，改由作者页面链接的 CDN 取得 7 页全文（SHA 见 receipt），不是只读摘要。
方法跨帧投影高斯混合深度分量，循环抽取 ensemble/MC-dropout 成员并增量维护均值方差。
作者实验涉及 TUM、KITTI、NYU 和多种较小网络；已有模型还需要 aleatoric/ensemble 支持。
缺少可靠基础方差时效果可差，pose 噪声也改变估计。仓库另注明 ensemble 初始化修正后的结果与原文不同。
依赖运动与对应关系，适合后续理论参考；本轮不把它作为独立于 R1 的 GT，不运行 UfM。

## DepthCov

Eric Dexheimer, Andrew J. Davison. *Learning a Depth Covariance Function*. CVPR 2023。
[CVF 论文页](https://openaccess.thecvf.com/content/CVPR2023/html/Dexheimer_Learning_a_Depth_Covariance_Function_CVPR_2023_paper.html)；
[全文备用](https://arxiv.org/abs/2303.12157)；[官方代码](https://github.com/edexheim/DepthCov)。
从图像学习非平稳 log-depth GP 协方差，显式保留像素误差相关性，用于稀疏深度条件化及联合优化。
方法及论文实验说明对角置信图不能表达完整相关性，但这是需要训练的协方差网络，
不能直接替代 Metric3D score，也不等同于 R1 的优化 Hessian 逆。本任务不训练其网络。
CVF PDF 访问受限，实际完整方法与实验通过 arXiv HTML 阅读。

## 方法选择

Native score 是最低额外 forward 成本；翻转 TTA 增加一次 forward，测的是输入敏感性；
depth-bin hook 不增加 forward，但额外存储/同步和统计不是零成本。
MC Dropout 要确认模型真实含有适合采样的 dropout，不能把 model.train() 当作免费、无副作用的方案。
Ensemble 通常要求独立成员或可解释的模型差异，当前只有一个固定 checkpoint，不能伪称 ensemble。
ECE 只在明确概率事件和合法校准后使用；单纯把 score 归一化到 [0,1] 不构成概率校准。
本轮候选优先顺序仍为 A→B/C→必要时 D，不根据未执行实验宣布某候选优于其他候选。
