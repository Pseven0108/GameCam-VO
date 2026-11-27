# Isolated integration boundaries

- Production DROID-W and TASK009 source/weights/results are read-only. The Task010 worktree starts from sealed commitff0c9ed7; no original CUDA extension is rebuilt or replaced.
- `run_window.py` is the v1 development runner; `run_window_v2.py` adds a separately named Full GeoMotion provider. `task010_fusion[_v2].py` multiplies BA observation weights, never overwrites native U or changes BA formulas. Each stage is explicitly tagged. Final BA and Filler remain native.
- `legacy_mean` uses the legacy gate's current-call mean as a uniform control. It is not same-state native BA replay. Neutral gates have p≤0.4 dead zone, p≥0.8 floor0.25. Geometry uses only valid lag2/4 evidence; unavailable evidence is neutral.
- `fusion` requires model/geometry agreement and uses remaining source-UBA support. `depth_fusion` maps to exactly that same gate with the independently admitted depth cache. Native U updates remain active in every group.
- `depth` is the separately admitted predicted inverse-depth blend. Its FiT3D files match original bytes. It is not CADP, a calibrated depth-confidence controller, or an unmasked pure-depth causal effect.
- Static targets use the previously admitted MDTracker interface and fixed0.15blend. This offline target-replacement intervention is distinct from observation-weight gating. Its manifest and predictions retain original RGB identities.
- Core transfer files and all methods/seeds/windows are SHA-frozen before held-out native execution. Later CPU analyses and publication helpers cannot change those interventions.

## Diagnosed launcher preparation issues

The first Unix-socket attempt on DrvFs failed; the corrected launcher uses ephemeral RAM IPC only. An early idle CPU helper expired before the later Full-model batch; no model had started. Preloading native classes installed the scatter compatibility package before the child, so the original install-once guard correctly rejected it. The correction preloads CPU dependencies/unchanged extension libraries only; each child independently installs the original compatibility path **before** importing native classes. The guard is not weakened or edited.

An initial `runpy` invocation left `__file__` relative, causing a source-receipt metadata error before model/CUDA initialization. The new numbered attempt resolves its script path first. Error capture was also moved inside the open log context. The initial empty log remains preserved rather than fabricated. A static-cache preparation check expected `receipt.json`; the admitted API actually uses `statistics.json`, `input_manifest.json`, `predictions.npz`. This check was corrected before transfer was frozen.

The actual readonly projection probe verifies self/cross-edge projection, Pose/Disparity/K preservation and CPU/CUDA RNG preservation. Each actual run is a fresh GPU process; neither model/video buffers nor a CUDA context are shared with the CPU preload server. Launch-source differences between initial CLI development and later paired transfer are recorded and are not advertised as bitwise R2 equivalence.
