# TASK011B complete actual review

Read FINAL_REVIEW.md, then10_FINAL_REPORT/TASK011B_DECISION.json. All140 planned
formal outcomes are real. R0/R1 cached auxiliary results and R3 VIPER camera
trajectory results are different evidence populations and are not pooled.

04_R3_VIPER_EVALUATION/evidence contains original logs, complete trajectories,
native BA-grid final states and exact full-image-ranked per-pixel coefficients.
Every derived grid is linked to the local full original archive and original
file SHA. Raw RGB, embedded-RGB fullvideo files, weights and environment
binaries are deliberately excluded. No claim is made that those inputs can be
recovered from SHA values. Complete source archives remain on the user's D:.

To replay the real R0/R1 numerical evidence without GPU/RGB/GT/model:

```text
python reproducibility/experiments/TASK011B/scripts/replay_saved_arrays.py --run 01_R0_TTA_VALIDITY/cpu_003 --output replay-outside-review.json
```

Use an output outside the sealed review. Native GPU reproduction additionally
requires the exact existing source/weights/environment and permitted original
VIPER inputs; it is not a synthetic or simulated replacement experiment.
