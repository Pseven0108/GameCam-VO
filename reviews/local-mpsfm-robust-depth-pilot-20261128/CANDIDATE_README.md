# Local MP-SfM-style robust depth-prior transfer

Independent DROID-W candidate, local RTX5060 8GB only. The ongoing remote
TASK011E-R4 is outside this task and is never contacted or modified.

The experiment compares BASE, A5, ROBUST and ROBUST_A5 on one existing
VIPER Train Day004 64-frame development window, seed43. Source and original
checkpoints remain frozen. See candidate/configs/PROTOCOL.json for the
prospectively fixed mathematical and execution contract.

This borrows the MP-SfM Cauchy robustification concept, not its complete SfM
system or its log-depth objective. Here a derived positive IRLS surrogate
robustifies the native linear disparity prior. Its residual-dependent weight
does not modify A5's separate damping branch.
