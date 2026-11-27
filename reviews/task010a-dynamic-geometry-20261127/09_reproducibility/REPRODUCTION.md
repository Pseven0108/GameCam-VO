# Reconstructing this bounded local study

Read `RESEARCH_PROTOCOL.md`, `METHODS_AND_STOP_RULES.md`, source-version snapshots and the final selection record first. This is a TASK009-derived **32-frame local engineering protocol**, not the sealed R2 full-sequence baseline and not a reproduction of any paper's benchmark table. No historical experiment is overwritten.

## Assets and environments

- Official source commits/archive hashes: `02_literature_and_code/SOURCE_SNAPSHOTS.json` and external model identity records. Model parameters, datasets, CUDA binaries and environments are not redistributed.
- Local Windows model forwards use the preserved `gamecam-vo` installation. Actual versions, precision, contexts, pixel cap, strict-load logs, per-window receipts and resource records accompany the review.
- Native tracking uses the preserved TASK009 WSL Python3.10 / PyTorch2.7.1+cu128 runtime and frozen DROID-W extension. No extension was recompiled. Windows PyTorch and native WSL PyTorch are different environments.
- Every input has original frame identity and a SHA record. The private dataset manifest contains local paths; the public roster omits machine credentials/raw data. Camera GT is a separate offline file and is not opened by model/SLAM scripts.
- VIPER camera indices are RGB−1 as inherited from the paired admission. Real Downtown frames are undistorted using published calibration; their reference poses use timestamps, linear position interpolation and quaternion SLERP. Metric accuracy beyond the published reference is not newly established.

## Execution order

1. Audit TASK008/009 with `diagnose_history.py`.
2. Admit the existing RGB/pose manifests. Run priors and separate model/flow jobs serially (`cache_priors.py`, `infer_candidates.py`, `flow_geometry.py`, `infer_static.py`). Official weights must pass their recorded SHA and strict loading.
3. Execute `seal_prediction_cache.py` and `audit_candidate_outputs.py` before using cached model fields. `depth_alignment_probe.py` independently admits the predicted-depth blend without GT.
4. Run `run_jobs.py --plan <explicit plan>` for v1 development. It rejects existing job logs, starts a new process for each run and stops on any failure. All original plans/commands/logs are preserved.
5. The optional CPU-preloaded **forkserver** launcher is admitted with separate CPU/CUDA probes before later paired transfer. The server loads no model/checkpoint/CUDA context; each run gets a new child and initializes all RNGs, model and video state itself. Do not use the unsafe `fork` method for CUDA. The first DrvFs Unix-socket probe failed; the corrected launcher uses a tiny ephemeral RAM IPC socket, while all persistent assets/temp/model outputs stay on D:.
6. Score only after inference using `evaluate_runs.py`, then `summarize_experiments.py`. Retain the designated preliminary baseline separately. Never pool BA events/pixels as independent experimental runs.
7. Freeze transfer candidates before scoring any held-out native trajectory. Keep game-unit and metre errors separate; use normalized ATE only for dimensionless within-window summaries. No interval receives its own scale fit.
8. Generate camera-flow, mask-proxy, per-stage and resource tables with the independent CPU scripts. Final source/weight protection, ZIP CRC and file-hash verification are mandatory before publication.

## Interpretation

Centered GMOS contexts, full-window static tracks and global predicted-depth alignment contain future information. These are **offline prototypes**. Cached-SLAM FPS excludes auxiliary-model inference; startup/import, model forward, transfer and serialization costs must remain separately visible. A full online implementation and full-sequence remote3090 validation are not established here.

No admitted motion/depth GT exists for these game windows. Precision/recall/F1/static-FPR, depth NLL/coverage and absolute-metric depth accuracy are unavailable. Geometry inlier support and flow-warp IoU are proxies, never GT replacements. WildWorld is an additional third-person **game** qualitative window, not the real-scene test.

Source documentation: [PyTorch CUDA multiprocessing](https://docs.pytorch.org/docs/2.7/notes/multiprocessing.html), [NVML-based CUDA check](https://docs.pytorch.org/docs/2.7/generated/torch.cuda.is_available.html), [Python forkserver preload](https://docs.python.org/3.10/library/multiprocessing.html#multiprocessing.set_forkserver_preload). Actual runtime probes, not API availability alone, determine admission.
