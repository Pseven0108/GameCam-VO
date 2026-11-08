# DROID-W reproduction deviations

Upstream: MoyangLi00/DROID-W `c3414af6047d06bafc1a6645d09f23247f3b2cdc`.
Branch: `repro/2026-10-31-sm120-readme`.

Initial changes: documentation-only corrections in README.md. Inline triple
backticks were changed to single backticks; the Bonn example now names the
existing `bonn_balloon.yaml` and includes `--config`, which run.py requires.
The unchanged original README and SHA256 are stored in the E7 source snapshot.
The automated selector still preferred unrelated evaluation/download commands;
none of those candidates was executed. Runtime must use the separately reviewed
official Bonn target, with the real Linux Python executable recorded explicitly.

Additional applied changes: root `setup.py` and pinned
`thirdparty/lietorch/setup.py` now delegate CUDA targets to PyTorch's
`TORCH_CUDA_ARCH_LIST=12.0`. The lietorch submodule has its own
`repro/2026-10-31-sm120` branch. This removes obsolete hard-coded targets and
builds the same kernels for the actual GPU, using one compilation job.

`src/utils/mono_priors/{img_feature_extractors,metric_depth_estimators}.py`
accept explicit local source paths through `GAMECAM_FIT3D_REPO` and
`GAMECAM_METRIC3D_REPO`. Unset variables retain upstream behavior. The selected
models, calls and weights are unchanged; local paths make the audited source
commits reproducible rather than fetching a moving Torch Hub branch.

Highest applied patch risk: low compatibility and source-path changes. No model,
BA, uncertainty, checkpoint or hyperparameter changes have been made. Individual
build attempts and the actual numerical CUDA checks determine the verification
scope below.

The actual second build failed in lietorch's CPU dtype dispatch: torch2.7
expects `c10::ScalarType` rather than `DeprecatedTypeProperties`. The reviewed
compatibility script changes `tensor.type()` to `tensor.scalar_type()` only on
dispatch macro lines in the pinned lietorch and DROID correlation extensions.
It leaves device checks, tensor values and all kernel math unchanged. The exact
changed files/counts and triggering compiler log are retained in
`logs/SOTA_setup/*_droid_aten_compatibility_patch/changes.json`.

Optional `GAMECAM_FRAME_TELEMETRY` in `src/tracker.py` appends each completed
frontend call's input index, timestamp, initialization flag and keyframe count.
This is observability only; it does not change any tensor, branch or model
parameter. File I/O is included in measured runtime. These records distinguish
frontend processing/initialization from trajectory-filler output coverage; they
do not invent a per-frame tracking-loss state that upstream does not expose.

Actual native probes additionally established:

- PyG's torch-scatter pt27/cu128 wheel requires GLIBC_2.32, while this WSL has
  glibc2.31. Rebuild the unchanged official 2.1.2 source at
  `140d3ad677aae615767412873b90982cbf97d35d` with this environment's compiler and
  `FORCE_ONLY_CUDA=1`. This upstream setup option still includes CPU dispatch
  sources inside the CUDA libraries; only duplicate CPU-only binaries are omitted.
- xformers0.0.31.post1's default FA3 dispatch fails on sm_120 with CUDA invalid
  argument. `GAMECAM_XFORMERS_DISABLE_FA3=1` invokes that pinned package's
  `_set_use_fa3(False)` before Metric3D loading. The remaining dispatcher passed
  an FP16 comparison against PyTorch SDPA; default FP32 also passed. This changes
  the computational attention backend, not the mathematical model. Timing and
  floating-point roundoff can differ from the author's stack. Original failures
  are retained in `logs/E7_*native_cuda_probe.log` and
  `logs/E7_lietorch_xformers_cuda_probe.log`.

The DROID backend subsequently built successfully after adding the existing
pip-installed NVIDIA include directories to CPATH. simple-knn then failed
because CUDA12.8 no longer exposes FLT_MAX transitively. Its
`repro/2026-10-31-cfloat` branch adds the standard `<cfloat>` include only; the
numeric constant and KNN implementation are unchanged. Triggering log:
`logs/SOTA_setup/20261030T172431_065343Z_droid_extensions/simple_knn.log`.

simple-knn then compiled successfully. Gaussian rasterization next required an
explicit `<cstdint>` include for std::uintptr_t/uint32_t/uint64_t in
`cuda_rasterizer/rasterizer_impl.h`, on its own
`repro/2026-10-31-cstdint` branch. No rasterization math was changed. Trigger:
`logs/SOTA_setup/20261030T173013_626217Z_droid_extensions/diff_gaussian_rasterization.log`.

Verified at `logs/SOTA_setup/20261030T173642_166507Z_droid_native_probe`:
all selected native extensions build/import, nonzero SE3 exp/log round trip,
CUDA scatter sum, tetrahedron KNN squared distances, identity-pose DROID frame
distance, and FP16/FP32 xFormers attention against PyTorch SDPA. Full SLAM
entry-point import and pip check passed. Gaussian rasterization itself is not
exercised because the official selected config disables mapping. Native setup
checks do not claim checkpoint inference or paper-result matching. Local prior
loading and frontend telemetry still require the actual Demo run.

The owned, opt-in `baselines/runtime_hooks/sitecustomize.py` records per-process
PyTorch allocator peaks on exit/unhandled exceptions. It does not alter tensors,
reset allocator peaks or catch/resume exceptions. Runtime also samples whole-GPU
usage; these measurement scopes are kept separate and shared IPC buffers are not
summed into a fabricated combined allocator peak.

The first actual official Bonn attempt loaded droid.pth and allocated the default
video buffers, then its spawned GPU worker failed rebuilding CUDA storage with
`invalid resource handle`. Evidence:
`results/E8_DROID_W/20261030T174752Z_official_bonn_balloon/inference_log.txt`.
The failed attempt and its whole-GPU/per-process telemetry remain intact.

`GAMECAM_SINGLE_PROCESS_TRACKING=1` in `src/slam.py` now calls the identical
`self.tracking(t_pipe)` in the main process for the existing one-GPU-worker,
mapping/gui/droidvis-disabled target. It preserves the function, call order,
counters, buffers, priors and all inference parameters while avoiding the failed
CUDA IPC transfer. It rejects configurations with extra GPU workers or GUI.
Owned CPU printer children are cleaned up in finally, including on failure.
This is an explicit OS/process scheduling deviation: runtime and memory can
differ from the author's spawned-worker execution, so it is not a paper-exact
performance reproduction. Verification requires the next actual official Demo.

The small independent CUDA IPC probe also failed on this host, confirming the
sharing issue without SLAM data or weights (`logs/E8_small_cuda_ipc_probe.log`).
The second official attempt using single-process tracking loaded Metric3D and
reached FiT3D/timm initialization, then timm0.9.10 rejected the installed newer
huggingface-hub API. Pin huggingface-hub to 0.25.2, verify its official PyPI
distribution hash and timm's actual Hub imports. This is a Python dependency
compatibility fix, with no change to the checkpoint/model selection.

Verified compatibility commits (local reproduction branches): DROID-W
`43c1425b7ea02633f87d70ed0d5fdf420b89a59e` (includes the first compatibility
commit `6be2460b56677b6e68d1fbe9379d91fe3e19b0f0` and the optional AMP cache flag);
lietorch `5cccb1a`; simple-knn `33385f0`; Gaussian rasterization `b7b5ec1`.
The third official Bonn Demo completed439/439 frontend calls and full poses,
final BA and trajectory filling, with53 keyframes. Independent keyframe inverse
consistency passed. MVS completion/evaluation is separately recorded. Original upstream
base commits and binary diffs are retained in source snapshot manifests, even
after these compatibility commits.

The first MVS100 attempt completed 98 frontend calls but hit the wrapper's
agent-selected 2400-second limit before writing a complete trajectory. It is
retained as an execution-timeout failure, not a tracking-loss or game-robustness
result. The wrapper now exposes a 7200-second execution budget.

`GAMECAM_DISABLE_AMP_WEIGHT_CACHE=1` in run.py is an opt-in resource option set
before autocast decorators are imported. It disables cached FP16 weight copies;
original FP32 weights and autocast FP16 computation are unchanged. An actual
MVS RGB-frame check on the frozen Metric3D, FiT3D, DROID fnet and cnet returned
bitwise-identical outputs in all four cases. Probe allocated peaks were
3,262,071,808 vs 2,421,059,584 bytes; one-call timings include warmup effects and
are not a speed benchmark. Evidence: reports/SOTA/droid_amp_cache_equivalence.json.
The next full MVS run records this execution option explicitly. No resolution,
buffer size, graph limits, checkpoint, model, loss or accuracy metric is changed.

Environment deviation under investigation: Python 3.10 with a Blackwell-capable
PyTorch 2.7.1 / CUDA 12.8 stack, in a project-specific WSL Conda environment.
This differs from the author's torch2.1/cu118 stack and will be labeled a
compatibility reproduction. Existing GameCam-VO's Windows Conda environment is
not modified. All model settings and weights remain the official selected ones.
