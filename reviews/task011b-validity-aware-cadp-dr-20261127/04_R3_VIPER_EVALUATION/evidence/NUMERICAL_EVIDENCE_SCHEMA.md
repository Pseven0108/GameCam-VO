# Public numerical evidence and exact coefficient interpretation

The complete original archives remain on the user's D: and are linked by whole/archive and member SHA. This public evidence is a documented exact selection of numerical fields, not a substitute containing recoverable raw RGB or full original video archives.

## Prior-cache grids

Each `priors/cache_<window>/<input-index>.npz` uses exactly y=3+8n, x=3+8n (45x80), matching the native disparity grid. Depth/confidence/validity values are selected directly, without interpolation. `flip_depth_aligned` and `flip_confidence_aligned` are unflipped into the native image coordinates. Full360x640 rankings are computed before grid selection; ranking only the published grid would not reproduce the actual controller.

`coefficient_A0` and `coefficient_A1` are the unit endpoint strengths. `coefficient_A2` through `coefficient_A5` are the exact float32 per-pixel reliability strengths supplied to the candidate. **`coefficient_A6` is the reliability r before geometry multiplication, not the final s=g*r.** Its r equals A4's rule at the same timestamp. The geometry multiplier is recomputed from each evolving A6 BA state and each internal iteration, so it cannot be represented as a single per-input-frame cache field.

## A6 geometry and effective prior

The original per-call `native_ba_calls.jsonl` contains `geometry_trace[iteration][active-source-row][field]`. The four fields are [g, u, positive-disparity valid-pixel count, native video slot kx]. The fourth field identifies the source slot explicitly; `keyframe_input_indices[slot]` maps that slot to the input timestamp and prior-cache file. `active_source_indices` is also retained. Two native internal iterations are preserved. For each matching source/iteration, the pixel strength is s=g*r. The native prior mask m is then applied to the curvature/gradient formulas. `effective_prior_mean_by_iteration` records the actual mask-weighted mean; it is not an independently calibrated depth probability.

## Final keyframe states and trajectories

`keyframe_state_ba_grid.npz` preserves native timestamps, poses/tum_poses, intrinsics, droid_disps and uncertainties; mono_disps is selected at the same exact native grid. These are final saved keyframe states, not all pre-BA intermediate tensors. Each original BA log retains the stated update/geometry/U summaries; full per-event residuals, Jacobians and complete state tensors were not exported and cannot be inferred from these summaries.

`trajectory.npz` contains64 original RGB IDs and their final exported c2w poses for a complete run. `initialization_partial.npz` is a genuine incomplete initialization state and must not be treated as a complete trajectory or filled by interpolation. The full140 outcome denominator is preserved. No model weight, raw dataset image or environment binary is included.
