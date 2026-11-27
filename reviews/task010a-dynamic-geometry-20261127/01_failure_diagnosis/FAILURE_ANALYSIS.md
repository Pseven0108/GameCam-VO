# TASK009 failure diagnosis — verified input-side facts

Historical results are sealed. `HISTORICAL_GATE_RECALCULATION.json` and `TASK009_GATE_CALL_SUMMARY.csv` are newly calculated evidence, not rewritten historical reports.

## What actually entered the solver

The TASK009 `DynamicObservationGate` multiplies the learned BA correspondence weight by `max(floor,(1-Mi)^alpha*(1-Mj)^beta)`. Default alpha=beta=1/floor0.1; the named weak variants use0.5/0.5/0.5. Neither predicted Pi3 depth nor its confidence enters this hook. It does not overwrite DROID native U, eta, intrinsics, pose or disparity. Source masks are sampled on feature coordinates and target masks at the current predicted correspondence, using explicit resize/stride transforms and original RGB identities. Out-of-bounds evidence is neutral. No direct wrong-time identity or logits-as-probabilities error was found in this path.

Both static-target and dynamic hooks operate on initialization, local BA, Final BA and Filler; the static target hook runs before mask sampling. The original experiment therefore did not isolate a single BA stage. MDTracker uses all32frames offline, and the forced keyframe schedule prevents conclusions about improved natural keyframe selection.

## Recalculated broad attenuation

First default gate mean=0.94646233; the edge-count-weighted mean over117calls=0.93998544. The first-call attenuated fraction is0.99999994, and every call is essentially100%. Recalculation at saved *actual target correspondences* confirms that even low source motion scores can receive mild attenuation. The raw source model score has median0.0075312; the nonzero background tail thus has a real mathematical consequence despite a small mean score.

This establishes an unconditional, widespread attenuation mechanism, not that every attenuated pixel was truly static. There is no moving-object GT in this window. Two-end multiplication also compounds ambiguous evidence rather than requiring independent geometric support.

## Native U relationship

The installed CUDA source maps source uncertainty with `clip(1/max(45U-35,0.1),0,1)` and optionally samples target U at the geometric projection. External gating therefore multiplies native UBA weighting. However, most saved source-U pixels are below the attenuation transition and retain native source weight1. One example has source-UBA mean0.99643 and only1.003% joint attenuation. It is **not established** that widespread double UBA suppression explains the entire failure. Complete target-end U and per-iteration native kernel weights were not saved in TASK009, so a full historical combined-weight map cannot be reconstructed.

## Evidence levels

| Finding | Level |
|---|---|
| Near-universal soft attenuation without a neutral region | DIRECT_LOG_AND_SAME_STATE_RECALCULATION |
| Separate source and predicted-target sampling; original frame IDs | SOURCE_AND_SAVED_ARRAY_VERIFICATION |
| External mask multiplies native UBA | SOURCE_CONFIRMED; source-end formula numerically recalculated |
| Pi3 confidence/depth absent from historical BA hook | SOURCE_CONFIRMED |
| Static-target hook changes correspondence before dynamic target sampling | SOURCE_CONFIRMED |
| Overattenuation is the sole cause of trajectory degradation | NOT_ESTABLISHED |
| Pi3MOS has poor GTA-V motion accuracy | UNVERIFIED_WITHOUT_MOTION_GT |
| A neutral region or geometry verifier will improve trajectories | HYPOTHESIS_TO_BE_TESTED |

New runs compare legacy, mean-only attenuation, neutral gating, geometry and static targets, including repeated baselines. Uniform same-mean attenuation is a control for changing total geometric strength relative to the unchanged depth prior; it is not a replay from a fixed native BA state. Native atomic numerical variation and closed-loop pose/U feedback remain confounds to a strong causal claim from a single run.
