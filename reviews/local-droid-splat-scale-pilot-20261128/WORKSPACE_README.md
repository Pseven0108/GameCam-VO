# GameCam-VO local DROID-Splat scale-alignment candidate

This workspace is isolated from the ongoing remote TASK011E-R4 and all frozen
DROID-W worktrees. It contains a bounded RTX5060 development experiment, not a
replacement baseline or a full DROID-Splat reproduction.

Read `candidate/configs/LOCAL_PROTOCOL_V2.json` together with
`SOURCE_FIDELITY_CORRECTION_V3.md` and `ALLOCATOR_AMENDMENT.md`. The V1 Day001
window was stationary and failed initialization; failed and inactive attempts
are kept. The common active input is VIPER Train Day004 RGB1658–1721, stride1,
640×360, seed43. All arms use the native Tracker, initialization, U/UBA, final
BA and trajectory filler. A common buffer96 is sufficient for64 input frames
plus16 filler slots; this does not redefine the remote buffer500 protocol.

Arms: BASE, A5, SCALE, SCALE_A5. The scale-only prior fit and A5 strength intervene
only in frontend main-loop local BA. No GT is loaded by the inference runtime.
Estimated-map scale alignment does not establish true metric scale.

`candidate/scripts/run_wsl.py` starts local Linux CUDA jobs with the existing WSL
environment. Common Metric3D/DINO caches are generated sequentially, to avoid
keeping prior networks and BA buffers simultaneously resident on an8GB device.
The local Metric3D optional xFormers call is replaced in memory by PyTorch SDPA;
FiT3D uses the complete, strictly loaded cached checkpoint. All new outputs,
builds and temporary files are on D:. Shared dependencies are read-only.

Examples (PowerShell, existing local environment):

```powershell
& D:\aaa\envs\gamecam-vo\python.exe candidate\scripts\run_wsl.py test_scale_controller.py
& D:\aaa\envs\gamecam-vo\python.exe candidate\scripts\run_wsl.py run_arm.py --arm SCALE --attempt 999
& D:\aaa\envs\gamecam-vo\python.exe candidate\scripts\evaluate_local.py
```

Each run requires an unused attempt directory. Do not rerun successful arms or
overwrite an existing evaluation. Derived output records, raw native call logs,
source snapshots and the final review explain the limits of this local study.

## Attribution

Scale/disparity least-squares alignment follows ChenHoy/DROID-Splat commit
`f0cb0316e1ee7f88f8a63c37a6fe19dd623e6eb2`, especially
`src/depth_video.py:591` and `src/geom/__init__.py:159` (Apache2.0).
The candidate deliberately uses shift=0 rather than the full affine or JDSA
system. DROID-W is frozen at `c3414af6047d06bafc1a6645d09f23247f3b2cdc`.
The A5 path is reused from GameCam-VO TASK011B, without changing its algorithm.

The original upstream licenses remain in `upstream/`; a review package includes
licenses and attribution but excludes weights, raw RGBs, caches, environment
binaries and compiled extensions.
