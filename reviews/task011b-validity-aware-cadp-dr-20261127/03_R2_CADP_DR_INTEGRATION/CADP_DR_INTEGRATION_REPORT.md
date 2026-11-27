# R2 integration: actual isolated native execution

A0 uses the original installed DROID-W extension. The official baseline already
contains Metric3D depth regularization. A1 is the independent candidate s=1 D1
endpoint. It is an implementation/trajectory variability control, not a separate
depth-enabled method or an invented D0 baseline.

Only frontend main-loop joint local BA is controlled. Initialization, second
initialization, native U/UBA, target weights, post-Schur damping, solve,
retraction, final BA and filler retain the frozen original implementation and
parameters. No pose-only or frozen-disparity experiment replaces the main design.

The unique candidate module is compiled separately; original droid_backends is
not overwritten. D0/D1 original repeats and cross-implementation pairs passed
the predeclared rtol1e-4/atol1e-5 in a real first-local-BA context, with two native
internal iterations and U updates retained. This local certificate does not
prove global bitwise determinism or supersede the historical R3 U-feedback
non-repeatability evidence. A0/A1 full-window differences must be reported.

Native CPU preprocessing plus CUDA float16 autocast is preserved. All20 A0
windows require a live first-frame Metric3D/cache bitwise identity and unchanged
CPU/CUDA RNG. Model construction and initialization remain native in every arm.
The shared prior cache eliminates repeated model forwards across methods; cold
end-to-end deployment runtime cannot be inferred from these cache-assisted times.

The native predictor's original cfg.cam.fx focal is retained, while tracker K
is the scaled calibration. This preexisting behavior is disclosed, not repaired
selectively for a method. Risk ranks and g are ordinal/inverse-normal proxies,
not calibrated probabilities or independently measured physical covariance.
