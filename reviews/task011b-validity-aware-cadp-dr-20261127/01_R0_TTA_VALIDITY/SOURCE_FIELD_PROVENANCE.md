| Field | Actual source / coordinates / meaning |
|---|---|
| native_depth | Official model canonical depth, unpad, bicubic to input grid, fx/1000, clamp0..300. Frozen output units are not independently certified physical metres. |
| flip_depth | Same restoration in horizontally flipped input coordinates; reverse the width axis exactly once before comparison. |
| native_confidence | Final raw model confidence, unpad then bilinear to native input grid; unbounded score, not a probability. |
| flip_confidence | Raw confidence in flipped coordinates; reverse width once for comparison; no depth scale factor. |
| flip_relative_disagreement | Original saved native-aligned T1 float32. Original invalid pairs remain NaN; raw historical zero extension is separate. |
| flip_log_disagreement | Original saved native-aligned log disagreement float32, invalid pairs remain NaN. |
| tta_valid | Exact original finite(native)&finite(unflipped flip)&native>0&flip>0, boolean on native pixel grid; all16 checked against original code and arrays. |
| native_bin_entropy | Initial 256-bin logits softmax entropy on154x266 bin grid; not final-depth calibrated uncertainty. |
| native_bin_variance | Variance of actual depth anchors under initial softmax; not final metric-depth error variance. |
| native_bin_max_probability | Initial largest softmax-bin mass; not probability that final depth is correct. |
| native_effective_bins | exp(initial entropy); bin-grid quantity, not 360x640 pixel depth reliability. |
