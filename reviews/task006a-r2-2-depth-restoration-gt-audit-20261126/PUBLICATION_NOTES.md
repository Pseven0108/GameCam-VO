# Complete R2.2 review delivery

The complete original ZIP is published as a Release asset. All28 NPZ files,
including16 full restored outputs, one native CPU fixture, five full-source-grid
examples and six full-resolution error/confidence maps, are preserved there.
The other118 sealed ZIP members are expanded here byte-for-byte, including all
reports, scripts, CSV data, figures, receipts and the internal SHA-256 manifest.
No raw input RGB/EXR dataset or checkpoint is redistributed.

[Complete original ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task006a-r2-2-depth-restoration-gt-audit-20261126/GAMECAM_TASK006A_R2_2_DEPTH_RESTORATION_GT_REVIEW.zip)

ZIP bytes: 298049439; members:146; internal SHA entries:145.
SHA256:160290adbc14770a8bbf3e9a1464b059f660b796d5eed6200d8ba3cf0c7baca3. CRC and all internal SHA entries passed locally.
Anonymous public readback is recorded separately in publication verification.

Start at FINAL_REVIEW.md.237 interpolation negatives/zeros became zero invalid
predictions, but mean AbsRel did not improve. Physical-metric GT remains unproven;
sequence0001 is already observed audit data, not a fresh independent test.
No new GPU inference, calibration fitting, detector training, CADP or BA changes.

R2.1 canonical source dependency: commit9e8e1f609796ed78a0a27b942d3d7440bcf23d72;
its complete original ZIP and raw datasets are not duplicated into this ZIP.
Visibility and default branch are unchanged; publication uses a new codex/ branch.
