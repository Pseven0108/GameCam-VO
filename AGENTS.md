<!-- VIPER_ONLY_CURRENT_SCOPE_20261127 -->
## Current research scope — user instruction, 2026-11-27

VIPER is the sole active experimental dataset. The user has abandoned the early third-person research direction and explicitly requested removal of its datasets and early experiments: WildWorld, OmniWorld-Game, DigiDogs and GameVerse. Do not resume, redownload or extend those retired branches automatically.

Old chat messages, historical commits, reviews and prior memory references about a third-person/WildWorld/OmniWorld mainline are historical context, not the current research plan. Do not infer a new task or dataset from them. Use the user's latest VIPER task and its approved frozen protocol. Keep existing VIPER data/results, shared baseline code/weights and environments protected. Real reference assets are retained but are not an authorization for new non-VIPER experiments. No new GPU run is authorized by this cleanup.

# GameCam-VO working agreement

Updated 2026-11-26, Asia/Shanghai, at the user's request.

## Execution tiers

- Default for bounded algorithm exploration: the local Windows NVIDIA RTX 5060 (8 GB), using the existing Conda environment `gamecam-vo`. After the user's 2026-11-27 storage migration, its Python executable is `D:\aaa\envs\gamecam-vo\python.exe`; the former C: path is a compatibility junction.
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
- Keep this project's environment, downloads, caches, temporary files and outputs on D:. Use `D:\aaa\envs\gamecam-vo`, `D:\aaa\caches`, and `D:\aaa\tmp\gamecam-vo`. Snapshot dependencies before changes; do not modify other Conda environments or the NVIDIA driver without task-specific need.
- See `docs/LOCAL_EXPERIMENT_WORKFLOW.md` for launch commands, validation evidence and limitations.

## Review delivery

- Publish the full original review ZIP and expanded review files to the Public `Pseven0108/GameCam-VO` repository, with fixed-commit links. Preserve existing visibility, default branch and sealed historical results.
- Exclude credentials, raw datasets, model weights and environment binaries. A research-stage approval and a publication approval are separate scopes.
- Verify published file/ZIP hashes and archive CRC before reporting delivery. Under the user's cleanup request, remove only the just-delivered local review ZIP copies after verified upload; retain expanded reports, code and experimental evidence.
- Never expose GitHub tokens in chat, command arguments, reports or Git. Use the dedicated authorized server credential wrapper for publication.
