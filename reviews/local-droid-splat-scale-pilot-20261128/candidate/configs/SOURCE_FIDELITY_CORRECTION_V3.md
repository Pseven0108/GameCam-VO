# Source-fidelity correction before trajectory scoring

SCALE_001 and SCALE_A5_001 completed, but the candidate activity audit found
that every fitted frame had fewer than the incorrectly applied **per-frame**
300-pixel gate. Therefore all scales were exactly identity fallbacks. Their
complete trajectories are preserved as inactive engineering attempts, not
selected for the final active scale-candidate comparison.

Two direct upstream differences were found in DROID-Splat commit
f0cb0316e1ee7f88f8a63c37a6fe19dd623e6eb2, src/depth_video.py:

1. reduce_confidence averages edge weights, then uses the x/y vector norm
   (lines440–469 and660–662), rather than averaging x/y components.
2. linear_align_prior checks the 300-pixel minimum over the entire selected
   map (lines608–615), rather than requiring 300 pixels in each individual KF.

Use the official vector norm and global support gate in the corrected transfer.
Once global support is sufficient, each scale-only scalar fit requires a positive
denominator and at least one eligible pixel. Zero-support frames still fall back.
Keep the existing .1 confidence threshold, .05 native multiview threshold,
2-view support, positive-disparity tests, positive scale>=.05 and shift=0.
Do not change neural weights, correspondence weights, U/UBA or BA formulas.

This source audit was performed before any comparative ATE/RPE evaluation.
It corrects an inactive transfer; it is not a threshold chosen to improve GT
scores. Retain original BASE_003 and A5_001, and run only the corrected SCALE_002
and SCALE_A5_002 candidates. Preserve the V2 controller in evidence/controller_v2_noop.
The gate correction is tested on independent synthetic confidence and mask data.
