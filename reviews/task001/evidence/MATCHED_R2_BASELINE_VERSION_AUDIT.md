# Baseline identity

- DROID-SLAM: `2dfd39f0dcad44012ca7bbb8aa70b55edbfa9c99`; native synchronous Droid, upstream demo parameters and 512-slot buffer.
- DROID-W: `c3414af6047d06bafc1a6645d09f23247f3b2cdc`; sealed upstream results, configs and checkpoint receipts.
- `evidence/RUNTIME_AUDIT.json` contains verified repository/submodule files, native extension hashes, environments and four weight hashes.
- Engineering changes are confined to staged pixels, launch, result export, observation and evaluation in this experiment directory.
- The initial 64-frame smoke exported 64 poses but the viewer failed to load `libGL.so`. A run-scoped library entry to the installed GL version fixed it.
  The upstream `Droid Visualizer` then rendered geometry on Xvfb/noVNC. The change was in the launch environment, without an upstream or algorithm patch.
- The native visualizer runs in a separate child and uses CUDA tensors for geometry. Recorded GPU samples are device totals, not a per-process attribution.
