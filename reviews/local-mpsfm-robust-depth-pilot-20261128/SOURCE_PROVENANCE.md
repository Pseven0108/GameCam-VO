# 官方来源与迁移范围

- [MP-SfM论文，CVPR2025](https://openaccess.thecvf.com/content/CVPR2025/papers/Pataki_MP-SfM_Monocular_Surface_Priors_for_Robust_Structure-from-Motion_CVPR_2025_paper.pdf)：C_reg使用Cauchy；C_int中的其他深度/法向项使用截断损失。本实验只取前者思想。
- [官方BA源码](https://github.com/cvg/mpsfm/blob/fa49640862391437865b2fd89ca3db3e6948b63b/mpsfm/sfm/mapper/bundle_adjustment.py#L22)：depth_loss_name=cauchy、rob_std=2；约L159-L176计算逐点损失尺度并使用logloss=True。
- [官方Metric3D-large配置](https://github.com/cvg/mpsfm/blob/fa49640862391437865b2fd89ca3db3e6948b63b/configs/defaults/m3dv2-large.yaml#L9)：相对噪声下限0.05。
- [官方depth.py](https://github.com/cvg/mpsfm/blob/fa49640862391437865b2fd89ca3db3e6948b63b/mpsfm/sfm/scene/image/depth.py#L75)：融合模型方差与相对噪声下限；这里没有迁移全套方差和绝对单位项。
- [Ceres2.2.0 CauchyLoss实现](https://github.com/ceres-solver/ceres-solver/blob/2.2.0/internal/ceres/loss_function.cc)：rho(s)=c²log(1+s/c²)，rho'=1/(1+s/c²)。本原型独立推导IRLS，不运行Ceres。
- [冻结DROID-W](https://github.com/MoyangLi00/DROID-W/tree/c3414af6047d06bafc1a6645d09f23247f3b2cdc)。

MP-SfM已从官方仓库新克隆，HEAD核验固定，未执行pip install、下载其模型或运行SfM。
source_reference保留选定源码、各自Apache2.0 LICENSE及原作者声明。
迁移不是官方实现的二进制复制，也不主张原作者实现了本轮candidate。
DROID-W208项blob审计及打包选择清单可复核；媒体/示例/模型资产不发布。
