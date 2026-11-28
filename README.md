# GameCam-VO: local DROID-Splat scale-transfer review

This independent review branch contains one completed local RTX5060 pilot.
It does not replace the default branch, the frozen DROID-W baseline, or the
ongoing remote TASK011E-R4. No remote instance was contacted.

**Result: the current scale-only transfer did not improve this window.**
On VIPER Train Day004 RGB1658–1721, Sim3 ATE was BASE=1.124538,
A5=0.759294, SCALE=1.465964, SCALE_A5=1.213120 (game units).
All four arms completed64 poses and retained the same52 keyframe IDs.

- [完整中文评审](reviews/local-droid-splat-scale-pilot-20261128/FINAL_REVIEW.md)
- [展开全部评审材料](reviews/local-droid-splat-scale-pilot-20261128/)
- [完整原始Review ZIP](review-packages/GAMECAM_LOCAL_DROID_SPLAT_SCALE_PILOT_REVIEW.zip)
- [ZIP SHA-256](review-packages/GAMECAM_LOCAL_DROID_SPLAT_SCALE_PILOT_REVIEW.zip.sha256)

Failed and inactive attempts, source, tests, trajectories and derived evidence
are retained. Raw images, model weights, environment binaries and credentials
are excluded. One Train window and one seed do not establish generalization.
