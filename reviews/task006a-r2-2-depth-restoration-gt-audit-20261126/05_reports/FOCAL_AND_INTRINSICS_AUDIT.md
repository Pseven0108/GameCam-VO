# Focal转换与像素网格：独立于插值的第二因素

固定Metric3D提交eb5b6fac0dc155e4e52f576e304fbf11655ff339的hubconf.py：
第160–163行将RGB缩放到canonical网格并同步缩放intrinsic；第193行bilinear恢复；
第197–199行用**缩放后fx/1000**转换深度并clamp[0,300]。
新下载该固定文件与封存文件SHA一致，均为b29ffc0530109bd55ce4067afd5dffd87fb2567416afb145e2cfdd0a1a0c8119。

封存DROID-W wrapper使用bicubic及未乘canonical resize的input fx/1000。
因此设置三个方案，保持变化可区分：旧bicubic；bilinear+相同focal；bilinear+官方resized focal。
不修改原始生产代码，不用GT精度选择插值或focal方案。

MVS的nominal resize=1.1083333333333334，VIPER=1.6625。
实际resized=598×1064，纵向因整数截断与nominal scale略有差别。
`02_restoration/FOCAL_AND_GRID_TRANSFORM_AUDIT.csv`逐帧保留source/input/resized/canonical尺寸及倍率。

half-pixel图像网格矩阵S具有translation=(sx/2-1/2,sy/2-1/2)；K'=S K。
canonical pad再左乘平移矩阵P。独立投影与roundtrip测试验证S、P组合，不将该推导冒称旧wrapper已经这样做。
官方示例中intrinsic乘nominal scale的写法与严格half-pixel K是不同约定，报告分别保留。

Calibration0000每方案拟合一个global scale后，常量focal倍率基本被scale吸收，
因而两个bilinear方案的0001误差几乎一致；这不能认证物理尺度。
另交付固定历史scale的`04_evaluation/FOCAL_FIXED_SCALE_SENSITIVITY.csv`，避免隐藏尺度变动。

R2.1网络输入使用torchvision Resize，官方示例使用OpenCV resize。
本轮固定已有网络输出，仅审计恢复/focal；不能称为完整官方端到端预处理复现。
若未来生产迁移，应单独冻结K、输入resize、focal和恢复约定，再申请GPU验证。
