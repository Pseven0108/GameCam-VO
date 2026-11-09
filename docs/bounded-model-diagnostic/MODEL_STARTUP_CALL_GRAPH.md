# 真实启动调用链（静态调查，未启动模型）

当前基线保持PARTIAL_PASS。下面按实际控制流排列，证据是本轮固定源码，不表示这些模型节点已执行。

|节点|源码位置|函数|输入|输出|CUDA|I/O或扩展|阻塞/风险|
|---|---|---|---|---|---|---|---|
|LAUNCHER_VALIDATION|GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/bounded_diagnostic_launcher.py:11|DiagnosticContext.validate_candidate|candidate+external permission|verified fixed identity|no|raw SHA+Git|may block in disk/Git|
|AUTHORIZATION_CONSUMPTION|GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/diagnostic_authorization.py:86|DiagnosticContext.validate(consume=True)|fresh one-shot evidence|exclusive nonce+session claim|no|0600 O_EXCL ledger|CPU identity hash precedes claim|
|WORKER_CREATION|GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/runner_core.py:103|supervise_once|claimed permission+exact command|child PID|no|subprocess logs|process startup|
|CHILD_VALIDATION|GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/bounded_diagnostic_child.py:9|DiagnosticContext.validate_child|candidate+parent+claim|one child claim|no|source hash+evidence+ledger|before torch import|
|TORCH_IMPORT|GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/bounded_diagnostic_child.py:73|bounded child main|pinned offline runtime|torch/cv2/numpy|potential library load|source and environment reads|can block under startup15s|
|CUDA_CONTEXT|GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/native_linux_guard_v2.py:16|Guard.__init__|cuda0+fixed UUID|context+heartbeat|yes|CUDA/driver|before network construction|
|STARTUP_PERMIT|GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/runner_core.py:120|supervise_once|two increasing CUDA samples+NVML|work permit|observes|session control write|startup barrier, not full model|
|DROID_NETWORK|GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/native_adapter_v2.py:117|DroidNet.__init__|unchanged architecture|CPU network|not until cuda|source only|CPU allocation|
|DROID_WEIGHTS|GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/native_adapter_v2.py:119|RuntimePins.boundary + torch.load|droid.pth|CPU state and load_state_dict|CPU checkpoint|raw SHA then guarded deserialize|weight file read|
|DROID_CUDA|GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/native_adapter_v2.py:124|Module.cuda/eval|loaded DroidNet|GPU network|yes|CUDA allocator|dynamic context/workspace|
|DEPTHVIDEO|GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/native_adapter_v2.py:134|DepthVideo.__init__|buffer350,H288,W512,feature384|shared CPU/GPU buffers|yes|multiprocessing Value/Arena+torch shared tensors|~2231MiB GPU/~960MiB CPU fixed cache|
|TRACKER|GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/native_adapter_v2.py:144|Tracker.__init__|SLAM namespace+native NoMapPipe|MotionFilter+Frontend+Backend|yes|TensorBoard output+prior checkpoint reads|prior constructor latency unknown|
|METRIC3D|baselines/droid_w/upstream/src/motion_filter.py:34|MotionFilter -> get_metric_depth_estimator|metric_depth_vit_large_800k.pth|metric depth estimator on CUDA|yes|local hub+guarded weight load|checkpoint/constructor dynamic memory|
|FIT3D|baselines/droid_w/upstream/src/motion_filter.py:37|MotionFilter -> get_feature_extractor|timm safetensors+dinov2 fine checkpoint|CUDA feature extractor|yes|local hub/timm/HF offline|relative order follows local pinned constructor|
|STOP_AT_TRACKER_DONE|GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/native_adapter_v2.py:148|PhaseRecorder.checkpoint|4 loader completions+Tracker returned|controlled unwind+terminal|observes|phase log+model/result.json|no forward, no BA, no frames|
|FIRST_RGB_NOT_AUTHORIZED|GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/native_adapter_v2.py:66|Stream.__getitem__ -> RGB_NoPose|fixed PNG/K|first frame CUDA tensor|yes|RGB only|NOT_REACHED in planned diagnostic|
|TRACKER_RUN_NOT_AUTHORIZED|GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/native_adapter_v2.py:191|Tracker.run|stream|motion filter/frames|yes|frame telemetry|NOT_REACHED|
|INITIALIZATION_NOT_AUTHORIZED|baselines/droid_w/upstream/src/frontend.py:127|Frontend.__initialize|12 accepted keyframes|local graph initialization|yes|native graph/BA extensions|NOT_REACHED|
|BA_NOT_AUTHORIZED|baselines/droid_w/upstream/src/depth_video.py:332|DepthVideo.ba -> droid_backends|graph constraints|optimized state|yes|native CUDA extension|NOT_REACHED|
|POSES_NOT_AUTHORIZED|GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/native_adapter_v2.py:40|snapshot|initialized real states|native estimated poses|yes|model result writes|NOT_REACHED; identity-filled buffers are not poses|

重要顺序：DepthVideo在Tracker之前；Tracker内部才创建Metric3D与FiT3D先验。四份权重全部完成不应在DROID主权重加载后提前宣布。已存在的上游遥测修改属于继承基线，本轮没有修改上游算法文件。
