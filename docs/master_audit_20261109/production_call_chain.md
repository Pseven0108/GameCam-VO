# Approved V2 call chain

launcher_v2.py -> LaunchContext -> runner_core.supervise_once(droidw) -> NVML barrier -> exclusive authorization claim -> native_child_v2.py -> independent child checks -> RuntimePins / prepared config / ModelIOBoundary / LoaderGate -> native CUDA/NVML Guard -> heavy Tracker imports -> unchanged native Tracker.run.

The current unarmed entry exits before candidate IO, output creation, subprocesses and Torch import. This is the approved Staging entrypoint; historical run.py and other raw upstream entrypoints remain reference code. Python hooks do not form a global OS security sandbox.

DepthVideo, DroidNet, Tracker, MotionFilter, network weights, native BA and all upstream baseline source bytes remain unchanged. The V2 adapter observes native frame boundaries and snapshots. It does not call trajectory filling, final BA or final refinement. DROID-W mapping is disabled.

RGB_NoPose produces RGB tensors, a synthesized all-zero depth placeholder and pose=None. Native Tracker ignores depth/pose sample fields. No GT, Skeleton, State or NPC/Monster data is supplied. Native timestamps are ordinals; no physical FPS is inferred.

The future interpreter uses a fresh session bytecode-cache prefix and -B; framework temporary files remain in session/tmp. All 512 MiB memory floors, the 3-second freshness rule, the 30-frame growth guard and the 15-second startup rule remain unchanged. The Guard now starts before heavy Tracker/prior imports so that their work is monitored.
