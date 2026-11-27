# Actual engineering issues and corrections

The initial CPU-only/GPU-unavailable checkpoint was never a completed downstream experiment. Its original reports are retained in HISTORICAL_CPU_BLOCKED_CHECKPOINT with historical labels. The final140 outcomes and numerical evidence supersede its current-status pointers only.

Early installation/launch attempts encountered offline model-cache resolution, spawn/Printer context and disk admission problems. Their diagnostics and partial evidence are retained. The installed original baseline and weights were not replaced. A unique candidate module and independent namespace were used.

The first10 completed engineering window pilots omitted MotionFilter's native CUDA autocast and initially preprocessed onCUDA. A real same-frame diagnostic found maxabs12.228088 and206138/230400 differing depth pixels versus nativeAMP. All10 were excluded from formal estimates before the corrected fixed batch; their source revisions, receipts and metrics remain in09_LOGS/EXCLUDED_FP32_PILOT_* and native diagnostics. Formal preprocessing runs onCPU, and the original no_grad/CUDA-autocast predictor path is retained. Every A0 window recomputes its first frame and checks exact cache equality and unchanged RNG.

The final evaluator rotates trajectory orientations by the same fitted global rotation as positions when reporting Sim3-aligned RPE. Known-transform CPU tests cover this behavior. The original camera GT and metric implementation remain preserved.

No selective windows, GT-fitted risk thresholds, retries after native failures, best-seed selection or failure deletion was used to make a method appear better. Algorithm failures remain in all140 completion denominators; paired accuracy tables show the available-pair N explicitly.
