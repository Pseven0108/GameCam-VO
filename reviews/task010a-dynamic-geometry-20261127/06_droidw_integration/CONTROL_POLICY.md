# Actual intervention parameters

The runner retains old CLI fields `gate_config` / `--gate` for historical TASK009 compatibility. Those fields are **not the active parameter source for every Task010 method**. Read the `method`, frozen source SHA and actual call logs together; in particular, the parser's historical floor0.1 is not the neutral/geometry/fusion floor.

| Method | Actual applied policy |
|---|---|
| baseline | No external target/weight intervention. |
| legacy | `max(0.1,(1-Mi)*(1-Mj))`, Pi3MOS; both endpoint samples. |
| legacy_mean | Same current-call legacy gate mean, applied uniformly. |
| neutral / gmos / geomotion / geomotion_full | Selected model, `p=max(Mi,Mj)`, severity=`clip((p-0.4)/0.4,0,1)`, gate=`1-0.75*severity`, floor0.25. |
| geometry | RAFT/FB/MAGSAC severity0 below1image-pixel Sampson residual and1 at4pixels; invalid/unsupported edges neutral; floor0.25. |
| fusion | GMOS severity × valid geometric severity × native source-UBA weight; final gate=`1-0.75*severity`. It is a heuristic evidence conjunction, not a product of statistically independent calibrated probabilities. |
| static | Existing MDTracker target blend0.15 with fixed visibility0.9 / dynamic0.1 admission; no new weight gate. |
| fusion_static | Static-target wrapper, then fusion weight wrapper. |
| depth | One predicted window-scale, static-mask supportM<0.4, ≥1024valid pixels/frame, temporal scaleP95/P05≤2, aligned depth ratio0.5–2,25%inverse-depth blend. No dynamic weight wrapper. |
| depth_static | The same depth cache and static-target intervention. |
| depth_fusion | The same depth cache and exactly the `fusion` weight policy. |

All gates act wherever the native wrapper is called, including initialization, local BA, Final BA and Filler. This is not a stage-isolated causal intervention. Original U/UBA, eta, native solver and gamma_depth0.01 are unchanged; native Final BA temporarily disables metric regularization as in the inherited baseline, then restores it before Filler. Confidence calibration and natural keyframe-selection improvements are not claimed.

The fusion coefficient uses the numerical source-U mapping regardless of the current call's `enable_udba` flag. When native UBA is disabled, that coefficient is still a conservative U-shaped heuristic; it is **not the actual active native weight**. Accordingly, this implementation is not an exact per-stage redundancy-removal algorithm or a reconstruction of native combined weights. The frozen code is not changed after observing this limitation.

The frozen transfer policy selects six named methods before evaluation and uses all three seeds for every arm/window. Publication and CPU-only analysis files are not additional algorithm changes.
