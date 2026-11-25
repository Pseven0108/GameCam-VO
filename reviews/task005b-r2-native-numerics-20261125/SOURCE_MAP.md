# 源码与证据映射

|位置（R1 task005b_kernels.cu行号）|作用|R2证据|
|---|---|---|
|1444附近 dino_feats_projective_transform_kernel|几何后的特征/不确定性导数|iter*_Jii_data、Jjj_data、kf_count|
|1645–1648 atomicAdd(Jjj_data)|向目标四邻点散射累加|全部6个观测配对的第一处分歧|
|1725–1761 linear_transform_kernel|J_total与feature/temp到J_linear|iter*_J_linear及之前的输入|
|1752、1755 atomicAdd(J_linear)|特征和bias的浮点归约|有差异，但输入J_total也已不同|
|1951–1952 ba_cuda|du与affine更新|iter*_affine_du、affine_before_linear/after|
|1022–1043 uncertainty_update_kernel|affine→temp→U|iter*_temp_after、U_after|
|1840附近 / 下次itr|新U进入projective_transform|iter2_U_before、Cii/wi/Hs/vs、dx/dz|
|2120起 ba_paths_cuda|R1 C/G候选|plain paths_1/2完整22字段/轮|

R2附带原R1候选完整源码以及只读观测生成脚本、差异、31字段顺序。观测reference删去记录后计算token与原函数一致。原安装关键函数正文的本次读取比对见SOURCE_BUILD_AUDIT.stdout.txt。

原安装.so SHA：6dcf8de36cadc2174023b649b026f04e61b1231420d98763cc5aa3b294a91c3e。
R1候选.so SHA：1edb9685e1569f2513a4dc895b2eddbe699e15d2d684079e4d9c2f77e9a4ad44。
R2观测.so SHA：6485409710451da8207154675ac7206f456ecb26bc4fc3baa82a6de12d1ea94c。
