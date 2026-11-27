# R1: actual validity-aware relative-risk comparison

Raw Native risk is -Confidence. Percentile=(average rank-.5)/N on the declared finite prediction domain, without GT or error. Flip ranks use only pair-valid pixels. Native ranks use Native-depth-valid/finite-confidence pixels. Equal Rank uses0.5/0.5, Max takes the larger rank. Parameters were fixed before this batch; no tuning on0001.

Pure Flip/Rank/Max diagnostic fields remain undefined outside their allowed domains. ValidityAwareFusion uses equal Rank on valid pairs and Native-only fallback otherwise. Invalid Native is always forbidden as a prior. For the full-GT *policy* diagnostic only, rejection is a separate maximum-risk sentinel1; this is not an inferred confidence or a zero disagreement. All five methods retain the same GT population and seven zero predictions. A second common-pair diagnostic explicitly excludes invalid pairs for mathematical comparison and is not a replacement for the failed strict gate.

## Previously observed MVS0001, three frame macro means

| method | AUROC_gt_0.2_mean | AP_gt_0.2_mean | AUSE_mean | AURG_mean | Spearman_mean |
|---|---|---|---|---|---|
| NativeOnly | 0.812186 | 0.483026 | 0.070793 | 0.013968 | 0.209433 |
| FlipOnly | 0.674258 | 0.374376 | 0.064675 | 0.020086 | 0.236267 |
| RankFusion | 0.784432 | 0.439087 | 0.059586 | 0.025175 | 0.263864 |
| MaxFusion | 0.802112 | 0.419851 | 0.057949 | 0.026812 | 0.215318 |
| ValidityAwareFusion | 0.784429 | 0.439084 | 0.059587 | 0.025174 | 0.263860 |

ValidityAwareFusion does not universally improve on either the historical Rank Fusion or the new pair-only Rank Fusion. Its small full-domain difference from pair-only Rank is solely fallback/rejection behavior; the two fields are exactly equal on common valid pairs. Symmetric TTA has a bounded numerical domain, but boundedness does not establish better ranking, calibration or VO utility.

All four disagreement definitions are saved and evaluated; SymmetricRelative was not replaced by a test-selected winner. AbsRel event thresholds0.1/0.2/0.5, raw-AbsRel AUSE/AURG, Spearman/Pearson, risk/error bins and20/40/60/80% retained coverage are in the CSVs. Native-only retains the stronger AUROC/AP here; Max has the lower AUSE. No method is a universal winner.

There is one reused evaluation sequence, not a new blind test or independent-domain generalization certificate. No VIPER dense-GT accuracy, probability calibration or temporal continuity is measured from the10 nonconsecutive images. Reliability=1-Risk is an ordinal control coefficient, not correctness probability.
