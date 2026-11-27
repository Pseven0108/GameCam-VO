# TASK010-A execution contract

2026-11-27, Asia/Shanghai. New authorization supersedes the historical prohibition on testing Pi3MOS in older research stages. Sealed results and the original production baseline remain protected.

- Development: previously inspected VIPER val007 RGB301–332 only. Do not call this an independent test or third-person camera sequence.
- Transfer evaluation: predeclared first32 frames of the existing Day004, Sunset007, Rain030, Night008 and Snow032 64-frame windows; Downtown1 and2, original ordinal600–631. No evaluation window is selected for a favourable model result.
- All model comparisons use the same admitted RGB IDs within a window, RGB[0,1], and explicit model-specific resize/context metadata. No test-GT fitting, no mask training, no claim of instantaneous-motion accuracy without labels.
- Native SLAM exploration inherits TASK009: 216-high input, buffer64, warmup6, forced keyframe every2, stride1, original tracker weights, gamma_depth0.01, native U/UBA, Final BA7+12 and original Filler. These runs are not a reproduction of the full-resolution R2 protocol.
- VIPER input384×216; real4:3 input288×216 after published-camera-model undistortion. K follows half-pixel resize; GT remains exclusively in an offline file that neither prior generation nor the runner opens.
- Predeclared alternatives: legacy two-end soft gate; a max-end gate with neutral region p≤0.4 and floor0.25 at p≥0.8; independent RAFT/FB/USAC epipolar evidence; model AND geometry evidence, with native source-UBA redundancy control. None replaces U, D, or the native solver. Scores are not calibrated motion probabilities.
- Geometry: FP32 official RAFT12updates, lags2 and4, forward/backward threshold1+0.05|flow| pixels; MAGSAC F with1pixel residual threshold. Zero evidence when F/FB is invalid. No motion-GT interpretation of residual alone.
- Static targets retain TASK009's pretrained MDTracker and 0.15blend/visibility0.9/dynamic0.1 filters. It is a separate offline, non-causal module, using predicted Metric3D depth, not ground truth.
- Repeat native runs across seeds43,44,45 on development before freezing transfer candidates. Keep all runs including failures. Do not interpret native atomic numerical variability as proof that a neutral hook helped.
- Transfer candidates and thresholds must be frozen before scoring held-out results. Aggregate performance by paired windows; raw metre and game-unit errors are never averaged together.
- Stop model-specific escalation on a reproducible interface/resource block, then use other admitted candidates. Stop an experimental method on data corruption, nonfinite poses, or exhausted local reserve; preserve outputs and choose an explicit new attempt only after diagnosing the issue.
- No new paid instance, server reboot/shutdown, production CUDA rebuild, baseline edits or data deletion. Local new assets stay on D:.
- Final reports must separate observed facts, same-state algebra, source-derived mechanisms and causal hypotheses. Negative results are publishable evidence; no improvement claim from selective windows.
