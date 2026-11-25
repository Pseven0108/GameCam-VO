# 源码映射

|函数|位置|
|---|---|
|projective_transform_kernel|02_candidate/task005b_r3_kernels.cu:187|
|dino_feats_projective_transform_kernel|02_candidate/task005b_r3_kernels.cu:1446|
|linear_transform_kernel|02_candidate/task005b_r3_kernels.cu:1725|
|uncertainty_update_kernel|02_candidate/task005b_r3_kernels.cu:1022|
|ba_r3_reference_cuda|02_candidate/task005b_r3_kernels.cu:2387|
|ba_r3_paths_cuda|02_candidate/task005b_r3_kernels.cu:2683|
|isolated_jjj_cuda|02_candidate/task005b_r3_kernels.cu:2984|
|isolated_linear_cuda|02_candidate/task005b_r3_kernels.cu:3007|

R1原函数正文位于新源码前缀，CPU合同核验一致。reference/paths相对R2差异见02_candidate/*_vs_R2.diff。原安装.so及R1/R2所有保护文件SHA见ORIGINAL_EVIDENCE_PRESERVATION.json；未以无.git目录的HEAD伪造提交核验。
