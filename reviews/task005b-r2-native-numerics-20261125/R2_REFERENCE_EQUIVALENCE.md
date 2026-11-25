# 原安装、ba_reference、ba_paths的对照

ba_reference绑定R1候选编译单元内的原ba_cuda。实际读取原安装旁的droid_kernels.cu，ba_cuda、linear_transform_kernel、uncertainty_update_kernel、dino_feats_projective_transform_kernel四个函数正文与R1候选完全一致（SHA见00_intake/SOURCE_BUILD_AUDIT.stdout.txt）。

当前编译器g++11.4、nvcc11.8.89、Torch2.1.0+cu118；独立候选-O3、sm86，无fast-math新开关。安装setup声明多架构，而候选只针对sm86；原安装二进制完整历史构建命令未在本轮重新恢复，因此不宣称二进制编译身份相同。

原安装vsreference：最终7字段2/4配对通过。原安装vs paths：0/4。reference vs paths：4/4。原安装自身重复0/1，故上述失败不能单独识别为重新编译或新增C/G代码错误。

新观测模块保留原R1源文件字节前缀，追加两个函数；删去记录语句后reference计算token与原ba_cuda一致，由CPU测试验证。paths只额外分离mc/mg mask。本轮两者C=G=0。

不能省略的有效输入区别：原扩展/reference的disps_sens全零，paths输入真实cached_mono再内部将mc/mg置零。其他有效实参SHA相同。两条路径的D0有效C/w语义相同；并非声称每个实参字节都相同。

观测副本的第一轮C/w/Q、dx/dz逐位一致，支持D0原公式的计算等价。第二轮U Native仍有超差，不能升级为全路径严格等价PASS。所有配对完整保留；不选择性省略失败结果。
