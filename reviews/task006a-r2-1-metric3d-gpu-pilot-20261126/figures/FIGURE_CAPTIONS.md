# Figure reading notes

All panels use actual saved outputs. VIPER has no admitted local dense-depth GT;
its heatmaps/histograms are descriptive only. Raw confidence is never sigmoid-normalized.
The five-environment plate shows the first preselected sample in each environment;
both selected frames per environment remain in raw outputs and numerical CSV.

MVS panels use the independently held-out sequence0001, with one global prediction
scale fitted on sequence0000 only. Native units are not certified meters. The strict
GT gate failed at seven zero predictions and remains FAILED. Secondary diagnostics
retain zero predictions as AbsRel=1 and infinite log error; no such pixels are removed.
TTA values for those points are separately recalculated from the user-defined epsilon
formula without rewriting the original saved NaNs. Display limits are only color limits:
depth0.5..100 baseline units, native-GT30..5000, TTA0..1, AbsRel0..1; arrays retain full values.

AUROC dots are three frames from ONE test sequence, not independent sequence replicates.
No statistical significance or cross-sequence confidence interval is claimed. Entropy
keeps its preregistered higher-is-risk direction even when AUROC is below random.
Source data are in 04_evaluation/diagnostic_zero_extension_002 and original NPZ files.
