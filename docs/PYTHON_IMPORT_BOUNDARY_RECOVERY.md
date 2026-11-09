# K6-A-GPU-R2 Python import boundary recovery

This phase fixes the failed initialization diagnostic's pre-model Python import path. It does not run DROID-W, construct a network or Tracker, deserialize a checkpoint, allocate CUDA tensors, submit RGB, or evaluate a trajectory. A new candidate and a fresh external one-shot GPU permission are required for any later diagnostic.

## Runtime changes

- Remove PYTHONPYCACHEPREFIX from the diagnostic candidate and strip an inherited value when building the child environment. Keep Python -B and PYTHONDONTWRITEBYTECODE=1.
- Use the trusted Python environment's normal cache paths for environment modules, read-only under the existing boundary. Sealed project modules compile directly from SHA-checked source; they do not read unpinned project pyc files.
- Pin MPLCONFIGDIR to model/matplotlib with MPLBACKEND=Agg. Pin general import temporary files to model/import_tmp after checking the original IPC fallback. The IPC arena directory chooser remains bound to the original session-owned /dev/shm root or session/tmp; no IPC policy, safety threshold, or Session file allowlist is widened.
- Allow descriptor-relative remove/rmdir only for an owned directory fd whose live /proc identity resolves inside model/import_tmp; disallow traversal and symlinks. Hard links remain prohibited. For a hard-link capability probe strictly inside import_tmp, deny with PermissionError so the dependency can report the capability unavailable and clean its own temporary files. Everywhere else the original hard-link rejection remains unchanged.
- Report preparation/import failures in model/result.json plus a hash-bound worker_terminal.json. Preserve the first error if traceback formatting or phase error telemetry fails. Never overwrite a pre-existing result. Diagnostic terminal validation accepts a bound failure while preserving the zero-frame/zero-BA scope; successful completion still requires all four actual weight loads and TRACKER_CONSTRUCTION_DONE.

## Focused validation

Use the actual Python 3.10.20 environment with CUDA_VISIBLE_DEVICES empty. The legacy cache configuration reproduces MODEL_SESSION_READ_OUTSIDE_ALLOWLIST. Real imports cover Torch, OpenCV, NumPy, native adapter/guard, DepthVideo, DroidNet, Tracker and dataset definitions. No constructors are invoked. A separate CPU-only fixture calls the production child's main with a nonpersistent mock context and replaces the native runtime with a hard stop before entry; it cannot create a real model permission or claim.

The recovery suite covers read-only import policy, poisoned source caches, changed source SHA, symlinks, descriptor traversal, hard-link denial, protected Session reads/writes, early-terminal binding, original-cause preservation and Supervisor cleanup. Reuse the existing small Session write boundary test; no broad IPC rerun is required. Detailed raw results, including intermediate failed CPU probes, belong to the external review bundle, not the source repository.

A CPU import closure around 13–14 seconds is not a model startup measurement and provides no guarantee about the unchanged 15-second CUDA startup barrier. DYNAMIC_MEMORY_PEAK_UNKNOWN and FULL_MODEL_STARTUP_TIMING_UNVERIFIED remain unresolved. The Python audit hook is not a native-code or OS sandbox.
