# R2.1恢复合同

当前GPU推理已完成16图/33forward，不能再当作尚未运行重做。
数据和源码在本目录，原始NPZ均在01_smoke与02_pilot；所有文件有SHA。
独立远端root：/root/rivermind-data/GAMECAM_TASK006A_R2_1_GPU_PILOT_20261126_R1。
当前SSH31136，本次未重启/关机实例，未来先重核SSH与GPU而不要求同一GPU UUID。

原严格评价失败留在04_evaluation根，不能覆盖；diagnostic_zero_extension_002是最终复算版本，
与001的结构化数值结果保持一致，来源SHA/执行时间另有区别。74个CPU测试是最新两个不同测试套件的61+13，
旧8项结果是13项套件的早期子集，不重复累计成82项。

GT来源：新0001完整300文件存在inputs/MVS-Synth；旧0000复用既有数据。
校准仅0000；0001已观察，不能后续调参再当新测试。物理米制仍BLOCKED；禁止把scale15.9855当单位真值。
任何后续方法不得从当前结果自动接入CADP、修改BA/CUDA或进入TASK007。
原权重、R2/YAML、历史结果与旧GT只读保护。原始RGB/GT/权重不上传，原始推理输出完整上传评审附件。
