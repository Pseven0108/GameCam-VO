# 复现与数据合同

本轮所有计算均CPU-only。Python3.9.13、NumPy2.0.2、SciPy、Pillow、OpenEXR、Matplotlib；
PyTorch CPU恢复使用已有远端2.1.0+cu118环境，CUDA_VISIBLE_DEVICES为空，无模型加载。

原R2.1依赖：Commit9e8e1f609796ed78a0a27b942d3d7440bcf23d72；完整ZIP
https://github.com/Pseven0108/GameCam-VO/releases/download/task006a-r2-1-metric3d-gpu-pilot-20261126/GAMECAM_TASK006A_R2_1_METRIC3D_GPU_REVIEW.zip
SHA256 fc8dfeb8e2746c8033621af9647a382e9e3138ff09bf46e8ddee453f678c7ae8。
该包提供canonical预测与padding/resize/K收据；原始RGB/GT需通过原官方数据来源及本地受保护目录获得，本包不分发。

新代码根目录由common.py的文件位置推导。默认作为GameCam-VO/reviews/<本轮slug>保存，
前轮R2.1及R2协议目录为相邻reviews目录；OpenEXR runtime_site复用前轮。
不携带模型权重，不执行torch.load，不读取封存C0，不导入DROID-W。

原始GT路径：data/mvs_synth/GTAV_540/0000；R2.1/inputs/MVS-Synth/GTAV_540/0001。
原始模型NPZ路径来自R2.1两份INFERENCE_RECEIPT.json，以SHA验证，不猜测文件匹配。

```powershell
$env:CUDA_VISIBLE_DEVICES=''
$env:PYTHONUTF8='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
& 'D:\Python\Python3\Python3.9.13\python.exe' -B code/run_tests.py
```

按目录从新副本复现：intake→collect_sources→remote_cpu_restore或现有torch_CPU输出→validate_restoration→
audit_gt→alignment_conditioning→precision_audit→full_resolution_audit→evaluate_restored→plot_results。
脚本采用exclusive create，拒绝覆盖已封存产物；已完成包不要直接原地全量重跑。
复现者应另建空目录，保留relative依赖关系；远端transport含本机历史路径/端点，需要显式配置可信主机密钥，不能自动接受新密钥。
无需远端即可读取本包已生成全部CPU数组和6帧逐像素误差图。

单位合同：raw GT native units，finite且>0；不插值GT，不填Inf，不按预测有效性删除GT点。
scale只由0000三帧的log-ratio中位数拟合；0001仅复用审计，无fresh-test claim。
fixed historical scale敏感性与每variant独立Calibration scale结果分别保留。

SHA清单覆盖封包内所有payload文件，清单自身不自哈希；ZIP外的PACKAGE_VERIFICATION和sha256 sidecar覆盖ZIP。
Git展开文件不含NPZ，所有NPZ均在完整Release ZIP；PUBLICATION_NOTES和发布清单记录对应身份。
