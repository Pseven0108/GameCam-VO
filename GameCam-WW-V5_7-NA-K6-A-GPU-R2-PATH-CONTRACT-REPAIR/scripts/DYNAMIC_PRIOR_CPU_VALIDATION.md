# Dynamic prior CPU validation

Run in the pinned server Python 3.10.20 environment with -B, PYTHONDONTWRITEBYTECODE=1, CUDA_VISIBLE_DEVICES empty, and PYTHONPYCACHEPREFIX unset. Dependencies are already installed; do not invoke model entrypoints or install new model code.

Targeted unit tests: test_dynamic_prior_import.py, test_import_boundary_recovery.py, test_bounded_diagnostic.py and test_startup_protocol.py. These cover same-byte verification/compilation, exact manifest binding, symlink/descriptor escape, actual ModelIOBoundary denials, normal package semantics, direct Hub scope/rollback and unchanged authorization/startup rules.

The actual-source CPU fixture is dynamic_prior_production_child_cpu_fixture.py. It runs bounded_diagnostic_child.main with an in-memory CPU test context and replaces _native_runtime before invocation. It imports real Torch/OpenCV/NumPy, real Metric3D hubconf/selected source modules, real FiT3D hubconf/timm DINO registry and DROID prior wrappers. It blocks CUDA initialization, torch.nn.Module construction, checkpoint deserialization and image/GT reads after static file-identity prechecks. CPU test telemetry is explicitly synthetic. It does not validate real GPU memory or complete Tracker construction.

The separate audit controller (included in the review evidence) owns Supervisor/monitor startup and IPC cleanup. Production candidate and authorization validation are tested separately; the CPU context creates no GPU permission, authorization nonce or one-shot claim. Negative CPU cases reproduce the old direct Hub failure, inject early import and hub-identity failures, deny Session reads, and exercise fixed preparation timeout and stale-monitor shutdown.

The dynamic prior source manifest contains 58 unchanged Metric3D/FiT3D Python source records from the previous candidate. Existing external torch_scatter build sources remain pinned. Unused facebookresearch/dinov2 and other model branches are not imported; network downloads remain denied. The selected source inventory and precise coverage are in the review JSON, not inferred from one hubconf import.
