# What “full raw evidence” contains

“Full” means **all frames and unaltered arrays actually saved by this task**, including negative results and failed-attempt receipts. It does not mean that every tensor in each model's entire `forward()` dictionary was captured. Do not reconstruct unsaved fields from screenshots or treat them as available.

| Provider | Preserved fields | Not captured / not used |
|---|---|---|
| GMOS-S | Original float sigmoid motion score, target/context RGB IDs | Full instance propagator, encoder token tensors and a metric-depth head are not provided by this adapter. |
| Pi3MOS | Original float motion score, selected sigmoid geometry-confidence map, local-point z, frame/context IDs | Local x/y, predicted camera poses and the complete returned world point cloud are not captured in this task. DROID predicted poses, not Pi3 poses, drive camera-flow diagnostics. |
| GeoMotion CVPR / Full | Float motion score, the corresponding raw motion logit under the generic saved key `confidence`, local-point z, IDs | This `confidence` is **not depth confidence**. Complete local x/y and model camera/world point outputs are not captured. Full's optional SAM2 post-refinement is not run. |
| RAFT / geometry | Original forward/backward flow caches, valid/FB/Sampson evidence and F | Not independently labelled object motion or true camera motion. |
| Metric3D / FiT3D | Every predicted depth and feature input used by the native runs, all receipts/identities | Metric3D confidence is not part of this cached-prior interface; no depth confidence calibration is fabricated. |
| MDTracker | Predicted tracks, visibility, input manifest and statistics | No GT motion decomposition, full author UniDepth pipeline or physically measured track depths. |
| Native DROID-W | Final keyframe poses/disparities/U, before-Final-BA poses, final full-frame poses, original configs/logs/timelines | Complete Schur/Jacobian/residual tensors and every native internal-iteration effective weight were not captured. Proxy support counts are explicitly labelled. |

The six RAW Release assets preserve all saved model/flow/prior/static fields byte-for-byte and include their SHA manifests. The main review additionally includes every native run, code/tests/reports, original logs and eight fixed float examples. Source checkpoints, original RGB datasets, reference GT and environment binaries remain excluded from redistribution.

The depth study compares baseline Metric3D with a conservative, static-mask-supported, globally scale-aligned inverse-depth blend. Pure external-depth replacement is not a separately validated VO arm. Static-track target blending is not the same as using static 3D tracks to certify depth scale. Missing GT prevents physical-depth accuracy and Confidence calibration claims. These limits are part of the result, not unreported successful experiments.
