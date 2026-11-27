# R3: data admitted, trajectory experiment not started

**20 windows, four per environment,20 sequences,64 contiguous frames each,1280 original JPEGs. Planned140 arm/window runs; actual0.**

Selection was frozen before any new model result: first four eligible constant-K complete Validation sequence IDs per environment, arithmetic temporal midpoint. No algorithm score, depth error or GT motion was used to choose them. Camera motion descriptors were calculated only afterward. This balances weather and sequence identity, but does not prove that all requested scene challenges (especially dynamic-object density) are covered; those still require visual descriptors or manual review. These are previously available Validation sequences, not a new official Test or blind holdout.

Only the1280 exact existing ZIP members were extracted. All member CRC and complete JPEG decode checks pass, original1920x1080 RGB is retained. Camera rows exist64/64 per window and CameraID=RGBID-1 holds. K deviations are below.001px. Known variable-K val042/043 are excluded before comparison. No dataset downloads or retired third-person assets are used.

Candidate common input:640x360, OpenCV INTER_LINEAR, no crop, half-pixel calibration as in the existing full-sequence input protocol. Native loader calibration must be compensated exactly as in the original input adapter. Pose labels stay in an offline scoring file; inference must receive only images, IDs andK.

ATE/RPE, success/failure, raw scale, Sim3 scale and drift are **unmeasured**. The three metric CSVs currently contain schemas only, with no score rows or invented zero results. R3_EXECUTION_LEDGER is explicitly140 planned/not-started entries, not a run log. CAMERA_ADMISSION motion numbers are GT-only input descriptors, not predicted performance.

After GPU readiness and native regression, finish the common cached native-depth/Confidence/flip provider with identity, preprocessing/focal and RNG checks. Then serially run all seven arms on this fixed list, retain every failure and original output, score full valid trajectories with the same existing SE3/Sim3 tools, and report scale separately. Do not use Sim3 alone as scale-improvement evidence. Group bootstrap by source sequence, not pixels or BA events. A possible outcome is no improvement; do not terminate merely because an auxiliary ranking is poor.

Uniform attenuation is not an eighth authorized arm. Since per-image ranks attenuate mean prior strength, any eventual utility gain must be interpreted with this limitation; selective-reliability superiority over uniform attenuation cannot be claimed without an additional controlled experiment.
