# Publication notes — TASK006A-R1

This directory publishes the complete CPU float64 CADP mathematical prototype,
tests, synthetic inputs/results, logs, provenance and original byte-exact review ZIP.

- Publication was separately authorized by the user after R1 completed on 2026-11-26.
- Statements such as "GitHub not published" in the sealed R1 execution records
  describe the original research execution, before this later publication.
- Those sealed reports/manifests and the original ZIP have not been rewritten.
- No GPU, model, C0 restore, R2, or new SLAM experiment is part of publication.
- Synthetic .npz arrays are generated research fixtures, not model checkpoints.
- README and PROJECT_STATUS in this publication branch supersede older branch
  status text. Existing branches, default-branch choice and Public visibility remain.

Start with [FINAL_REVIEW.md](FINAL_REVIEW.md), then
[MATHEMATICAL_DERIVATION.md](MATHEMATICAL_DERIVATION.md) and
[CPU_TEST_AND_EXPERIMENT_REPORT.md](CPU_TEST_AND_EXPERIMENT_REPORT.md).
Full ZIP: [GAMECAM_TASK006A_R1_CADP_CPU_REVIEW.zip](../../review_packages/GAMECAM_TASK006A_R1_CADP_CPU_REVIEW.zip).

Mathematics passes under the stated regularized precision definition. This does
not certify native CUDA/U endpoint equivalence, native estimator covariance or
improved real-world SLAM accuracy. Retain the inaccurate-prior counterexample.
