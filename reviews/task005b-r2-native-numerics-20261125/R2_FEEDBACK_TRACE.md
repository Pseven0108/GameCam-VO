# 第二轮反馈：最早差异与传播

观测函数各一次调用内部保留两轮，每轮31字段；两份reference、两份paths，共4份trace、6个配对。

1. 第一轮Pose、disps、U、temp、affine输入逐位一致。
2. projective_transform的Cii/wi/Hs/vs逐位一致，深度C/w/Q、dx/dz及几何后Pose/disps逐位一致。
3. Jii_data逐位一致，**Jjj_data首次不同**。Jjj由DINO特征重投影向目标像素atomicAdd累加；四个双线性邻点分别累加。
4. J_total受到Jjj扰动。linear_transform_kernel又使用atomicAdd累加J_linear；此处输入J_total已经不同，故不能仅用这组trace单独量化linear_transform自己的归约噪声。
5. du=-lr*mean(J_linear,0)；affine <- affine + (du-weight_decay*affine)。记录affine_du和前后affine，CPU按原算式复算。
6. temp=sum_c affine[c]*feature[c]+bias，U=log(1.1+exp(temp))。原生U Native实际联合更新affine/temp/U，而非单一U独立因素。
7. 第一轮更新后的U/temp/affine与同次调用第二轮入口逐位一致。第二轮入口Pose/disps仍相同，U等已不同，几何权重和正规方程因此可能不同。
8. 第二轮dx/dz出现微小变化，部分越过原容差。

四份观测重复的共同最早差异均在Jjj输出，但只观测到输出，未捕获atomic执行顺序。归因等级：源头输出已定位；浮点归约顺序是强支持解释；两处atomic的独立贡献尚未干预隔离。原安装.so无内部记录，不声称直接观测了该二进制内部Jjj。

CPU用同一封存DINO feature storage直接解码浮点字节，不导入torch：40/40公式检查通过。FP64累加只作独立算式参照，不替代某次FP32 atomic顺序。完整结果FEEDBACK_RECONSTRUCTION.csv。

观测复制采用detach().cpu().clone()，会同步GPU、增加CPU工作。它不改变优化公式，但可能改变调度。OBSERVER_EFFECT_ENDPOINTS.csv保留所有未埋点/观测最终字段对照，不把观测通过率混入原安装重复性。

72维线性系统CPU谱分析使用Eigen LLT对应的lower自伴语义，不平均上下三角。系统SPD，条件数约2.64e5–2.67e5；见LINEAR_SYSTEM_CONDITIONING.csv。条件数解释敏感性，不足以唯一归因。
