# Preserved engineering corrections

1. cpu001 stopped on metadata quantiles of a boolean validity field (NumPy disallows boolean interpolation subtraction). Quantile input was cast to float64 without changing the original dtype or any mask. A regression test was added. Original log retained.
2. cpu002 used the slow frozen Python per-tie loop. Only that owned CPU process was stopped after identity verification; partial arrays and receipt remain. Equivalent vectorized within-tie prefix accumulation was checked against the frozen reference on multiple sample sizes. No score/mask/threshold changed.
3. cpu003 is the completed actual batch (158.53s). It produced240 real metric rows. The stopped/failed CPU passes are engineering attempts, not independent scientific repeats or GPU retries.
4. The execution-config helper initially duplicated its arm dictionary key; corrected before sealing the seven configurations, with no model execution or change to numerical outputs.
5. Initial figure QA caught automatic color cycling changing weather colors across groups. A fixed weather palette and categorical mask ticks were applied, and the actual figures were regenerated. Numerical data did not change.

The existing main worktrees were not reset/cleaned/stashed. The new shallow sparse repository's initially unpopulated index was initialized from its own HEAD; no main-tree deletion was committed. Main and all historical public Releases remain unchanged.
