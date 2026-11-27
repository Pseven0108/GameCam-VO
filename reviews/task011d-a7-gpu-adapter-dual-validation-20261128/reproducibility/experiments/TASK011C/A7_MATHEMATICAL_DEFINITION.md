# A7: same-state native-grid uniform attenuation

For one actual BA call, retain the frozen native source set
`kx = unique(sorted(arange(t0,t1) union ii))`; `jj` is not substituted for `ii`.
Resolve every live slot through its exact window-relative input timestamp. Sample
the unchanged A5 field and native-valid field with the original video's `slice_h`
and `slice_w`, onto the native disparity grid (normally 45x80).

For source slot t and native-grid pixel x:

```
M_t(x) = (mono_disparity_t(x) > 0) AND native_depth_valid_t(x)
r5_t   = unchanged TASK011B A5(native, unflipped_flip, confidence, tta_valid)
mu_t   = FP32_mean(r5_t(x), x in M_t)
r7_t(x)= mu_t inside M_t, zero elsewhere
```

Do not take a 640x360 whole-image mean, average different frames together, use
non-source slots, or freeze the mask at cache-generation time. The adapter reads
the native mono-disparity mask on every call. Empty M means no prior; its valid
mean is recorded as null, not an invented observation.

A5's pair-invalid native-only fallback is computed **before** uniformization.
After uniformization A7 intentionally has no per-pixel fallback value: every
pixel in M shares the mean. Original native-invalid support is never enabled.

The independent audit computes float64 statistics on the actual FP32 output:
each source mean, eligible-weighted call mean and dense source-grid call mean
must match within absolute 1e-6, with no tolerance relaxation or correction term.
Every positive-support mask must also remain equal, and A7's nonempty valid field
must be exactly constant. The inherited rank mapping is strictly positive on
finite-confidence valid pixels. A nonfinite confidence can instead produce an
A5 zero within M; filling it with a positive mean would violate positive-support
equality. The adapter stops in that case rather than redefining M or silently
enabling the rejected pixel. Nonfinite native mono disparities likewise stop;
no baseline data are repaired.

The unchanged native candidate uses s=r7 only in:

```
C = C_geometry + m*s*alpha + (1-m*s)*eta
b = b_geometry - m*s*alpha*(d - d_m)
alpha = 0.01
```

Geometry Need is false. Native solver iteration count, U/UBA, weights and original
30 positional BA arguments are forwarded unchanged; A7 adds only `strength, true,
false`, preserving the existing TASK011B candidate interface. Initialization,
motion-only BA, online global BA, final BA and filler use installed native BA.

## What mean matching proves, and what it does not

It matches scalar effective prior intensity against the **counterfactual A5 field
on this exact BA input state**. Spatial association with residual/geometry remains
different: equal scalar means do not imply equal curvature matrices or gradient.
That distinction is the intended research intervention.

Two independent full runs can choose different keyframes, masks and call schedules.
This implementation cannot certify that call k in the independently evolved A5
run has the same mean as call k in A7. It does not align unequal states or force
shared keyframes. If the review requires that stronger cross-run statement, a
separately approved fixed-state/shared-schedule design is needed. It is not
silently substituted into this total-frontend-effect protocol.

CPU evidence is an adapter/math certificate only. Actual CUDA device reductions,
native endpoint equivalence, and end-to-end trajectory utility remain untested.
