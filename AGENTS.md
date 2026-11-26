# GameCam-VO working agreement

Updated 2026-11-26, Asia/Shanghai, at the user's request.

## Execution tiers

- Default for bounded algorithm exploration: the local Windows NVIDIA RTX 5060 (8 GB), using the existing Conda environment `gamecam-vo`. Its Python executable is `C:\Users\Administrator\.conda\envs\gamecam-vo\python.exe`.
- Use the local CPU for GT/data audits, preprocessing, metrics, statistics, plots, unit tests and float64 mathematical prototypes.
- Use the remote RTX 3090 (24 GB) for approved full DROID-W runs, long-sequence BA, full datasets, large ablations and final paper experiments.
- An available local GPU does not authorize a new research stage, training or new data access. Follow the current task's scope and stop conditions.
- Do not start, stop, reboot or change the allocation of a remote instance unless the user requests it. No-card startup is intentional when selected.

## Local GPU practice

- Check the actual environment, device, free VRAM and other processes before a new GPU workload. Do not terminate other applications to make room.
- Start exploratory inference at batch size 1. FP16/autocast and sequential TTA are candidates that require a model-specific numerical check. Preserve the approved precision, resolution and intrinsics in formal comparisons.
- Basic CUDA tests do not prove that Metric3D or DROID-W fits in 8 GB. Measure each model separately before increasing workload.
- Native Windows compatibility, Linux CUDA extensions and cross-process CUDA sharing are separate checks. Do not copy the remote CUDA 11.8 environment or treat the local PyTorch build as an equivalent formal baseline.
- Keep checkpoints and datasets unchanged. Do not compile over a frozen baseline extension, change U/W/frontend/backend, or alter an approved protocol for environment convenience.
- Keep downloads, temporary files and outputs on D: when practical. The existing Conda environment itself remains in its original location. Snapshot dependencies before changes; do not modify other Conda environments or the NVIDIA driver without task-specific need.
- See `docs/LOCAL_EXPERIMENT_WORKFLOW.md` for launch commands, validation evidence and limitations.

## Review delivery

- Publish the full original review ZIP and expanded review files to the Public `Pseven0108/GameCam-VO` repository, with fixed-commit links. Preserve existing visibility, default branch and sealed historical results.
- Exclude credentials, raw datasets, model weights and environment binaries. A research-stage approval and a publication approval are separate scopes.
- Verify published file/ZIP hashes and archive CRC before reporting delivery. Under the user's cleanup request, remove only the just-delivered local review ZIP copies after verified upload; retain expanded reports, code and experimental evidence.
- Never expose GitHub tokens in chat, command arguments, reports or Git. Use the dedicated authorized server credential wrapper for publication.
