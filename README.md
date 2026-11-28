# GameCam-VO local MP-SfM-style robust-prior pilot

2026-11-28. Independent local RTX5060 experiment, 4 new64-frame trajectories.
**Current transferred candidate did not improve the baseline or A5.**

| Arm | Sim3 ATE (game units) | SE3 ATE |
|---|---:|---:|
| BASE | 1.126113 | 4.547552 |
| A5 | 0.759441 | 1.839610 |
| ROBUST | 1.744925 | 10.785689 |
| ROBUST_A5 | 1.863444 | 11.221772 |

- [完整中文评审](reviews/local-mpsfm-robust-depth-pilot-20261128/FINAL_REVIEW.md)
- [全部展开材料](reviews/local-mpsfm-robust-depth-pilot-20261128/)
- [完整Review ZIP](review-packages/GAMECAM_LOCAL_MPSFM_ROBUST_PILOT_REVIEW.zip)
- [SHA-256](review-packages/GAMECAM_LOCAL_MPSFM_ROBUST_PILOT_REVIEW.zip.sha256)

One Train window/seed43 only. This is a Cauchy-on-native-disparity transfer,
not a complete MP-SfM reproduction. No promotion into the frozen DROID-W.
The ongoing remote TASK011E-R4 was never contacted or modified.
Source, all4 attempts, logs, intermediate IRLS evidence and exact scores are included;
raw RGB, weights, environments, compiled extensions and credentials are excluded.
