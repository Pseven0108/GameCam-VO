# Independent geometry and camera-flow diagnostics

Two different geometric quantities are deliberately separated.

1. The **integrated gate** uses independent FP32 RAFT forward/backward flow, robust fundamental-matrix estimation and Sampson residual. FB-invalid, missing or degenerate evidence is neutral. Only lag2/4 edges are supported. It does not use camera GT, and it is not full RoMo or DynOSeg.
2. The **diagnostic camera-flow residual** uses the saved DROID-W world-to-camera pose and disparity after native Final BA, the actual feature-grid K and RAFT flow. It checks `Tji=Tjw*inverse(Tiw)` and projects rays using `Rji*rays+tji*disparity`; no GT pose/depth enters this calculation. Disparity-floor and invalid projections are excluded, never interpreted as moving pixels.

The second diagnostic is not fed back into these integrated gate runs. It exposes why a large residual is ambiguous: bad predicted camera pose, bad depth, occlusion, optical-flow error and independent motion can all produce it. The current integrated geometry gate is an epipolar verifier, not a claim that accurate dense camera-induced flow was recovered online.

An epipolar residual cannot detect every dynamic object: independent motion along the epipolar line can remain geometrically consistent. A dominant moving object can contaminate F; low parallax, planar scenes and pure rotation can be degenerate. Requiring model AND geometry evidence protects against some unsupported semantic masks but can lose true dynamic support. Neutral fallback prevents invalid data from becoming an arbitrary large penalty; it does not make the valid evidence perfect.

`CAMERA_FLOW_RESIDUAL_STATISTICS.csv` and `camera_residuals/` contain actual flow maps and valid-pixel summaries. Static/dynamic residual distributions are **not identifiable** without moving-object labels. Saved BA observer support counts are geometric proxies, not counters from inside the native kernel.
