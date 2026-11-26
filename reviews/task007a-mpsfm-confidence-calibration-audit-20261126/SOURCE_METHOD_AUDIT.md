# MP-SfM 原始方差映射与实现范围

## 固定原始来源

- [MP-SfM，CVPR 2025官方论文页面](https://openaccess.thecvf.com/content/CVPR2025/html/Pataki_MP-SfM_Monocular_Surface_Priors_for_Robust_Structure-from-Motion_CVPR_2025_paper.html)
- [官方Metric3Dv2适配器，固定Commit fa49640862391437865b2fd89ca3db3e6948b63b](https://github.com/cvg/mpsfm/blob/fa49640862391437865b2fd89ca3db3e6948b63b/mpsfm/extraction/imagewise/geometry/models/depth/metric3dv2.py)
- [官方Depth单先验路径，同一Commit](https://github.com/cvg/mpsfm/blob/fa49640862391437865b2fd89ca3db3e6948b63b/mpsfm/sfm/scene/image/depth.py)

通过GitHub连接器读取官方源码、配置及LICENSE，没有克隆或运行MP-SfM、没有下载其权重。
原始源文件以Git Blob SHA和SHA256核验，见 `sources/MPSFM_SOURCE_PROVENANCE.json` 及 `evidence/SOURCE_SNAPSHOT_VERIFICATION.json`。
CVF PDF及补充材料本轮直接打开遇到403；不将未读取部分当作证据。

## 模型适配器的直接定义：CONFIRMED_SOURCE

`Metric3Dv2.step`先移除padding、双线性恢复空间网格，然后恢复深度尺度并将恢复后的Confidence截到[0,1]：

\[
 c_* = \operatorname{clip}(c,0,1),\qquad
 \sigma_{raw}=d(1-c_*),\qquad v_{raw}=\sigma_{raw}^2.
\]

恢复网格与clip的顺序不能互换。d是该适配器输出的深度，v的单位是深度单位平方；c不是成功概率。
模型适配器本身在c>=1时给出零方差，因此不能直接将v_raw倒数送入Gaussian NLL或BA。

## 后续单先验路径：CONFIRMED_SOURCE

当prior_uncertainty=True、flip_consistency=False、depth_uncertainty非空且输入为有限正深度时，`Depth._init`包含：

\[
v_1=\max(a^2v_{raw},(r d)^2),\qquad
v_{out}=s^2\operatorname{clip}(v_1,n^2,M^2).
\]

没有max_std时没有上界。类默认a=3.33、r=0.0263、n=0.02、s=1。
这是当前官方源码的参考配置，不能直接当作VIPER或本项目Metric3D-L的拟合参数，也不是GPU数值等价性证明。
绝对floor n和上界M随深度单位改变；换单位只缩放d而不缩放n/M，公式不再有一致的单位语义。
在DROID-W的逆深度变量中使用深度方差还需要另行处理变量变换；本轮没有接入任何BA。

本包 `code/mpsfm_variance.py`只实现上述有限、正值、已对齐的单先验代数。
不复刻连续性mask、sky/valid选择、零深度替换、keypoint采样、双先验融合、相机网格变换或SfM优化。
源代码是参考依据，独立实现没有导入torch或模型；22项测试只证明这些已声明代数与边界合同。

## 未建立的结论

没有拟合校准系数、没有统计方差证书、没有VIPER NLL/覆盖率结果，也没有证明Gaussian残差、独立像素或跨环境泛化。
未经校准的单调风险分数可以有好的排序指标，同时仍然严重失准；反之，clip导致分数饱和也不能单独证明预测错误。
