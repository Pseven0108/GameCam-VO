# Recorded failures and accuracy regressions

No failed preparation is presented as a successful model/BA run. Original logs, empty pre-model output and explicit new attempt IDs are retained. See INTEGRATION_AUDIT and FINAL_REPORT for diagnosed preparation issues.

| Window | Method | Mean ATE | Baseline mean ATE | Reference unit |
|---|---|---:|---:|---|
| sunset007_holdout | geometry | 3.551059 | 3.103839 | VIPER game units, not verified metres |
| rain030_holdout | legacy | 0.048350 | 0.027890 | VIPER game units, not verified metres |
| rain030_holdout | geometry | 0.033525 | 0.027890 | VIPER game units, not verified metres |
| rain030_holdout | depth | 0.047656 | 0.027890 | VIPER game units, not verified metres |
| rain030_holdout | static | 0.042740 | 0.027890 | VIPER game units, not verified metres |
| rain030_holdout | depth_fusion | 0.056546 | 0.027890 | VIPER game units, not verified metres |
| night008_holdout | geometry | 3.610806 | 3.244683 | VIPER game units, not verified metres |
| night008_holdout | depth_fusion | 3.664273 | 3.244683 | VIPER game units, not verified metres |
| snow032_holdout | geometry | 0.215285 | 0.209992 | VIPER game units, not verified metres |
| snow032_holdout | depth | 0.218481 | 0.209992 | VIPER game units, not verified metres |
| snow032_holdout | depth_fusion | 0.213014 | 0.209992 | VIPER game units, not verified metres |
| downtown1_holdout | geometry | 0.011093 | 0.010930 | Published FAST-LIVO2 reference metres; not independent metrology |
| downtown1_holdout | depth | 0.011471 | 0.010930 | Published FAST-LIVO2 reference metres; not independent metrology |
| downtown1_holdout | static | 0.011447 | 0.010930 | Published FAST-LIVO2 reference metres; not independent metrology |
| downtown1_holdout | depth_fusion | 0.011129 | 0.010930 | Published FAST-LIVO2 reference metres; not independent metrology |
| downtown2_holdout | geometry | 0.014851 | 0.014720 | Published FAST-LIVO2 reference metres; not independent metrology |
| downtown2_holdout | depth | 0.014946 | 0.014720 | Published FAST-LIVO2 reference metres; not independent metrology |
| downtown2_holdout | static | 0.014777 | 0.014720 | Published FAST-LIVO2 reference metres; not independent metrology |
| downtown2_holdout | depth_fusion | 0.014986 | 0.014720 | Published FAST-LIVO2 reference metres; not independent metrology |

These are completed-run accuracy regressions, not crashes. Every one remains in the primary tables. Missing motion/depth GT, forced keyframes, short windows, source-U coefficient/UBA-enable mismatch and offline future information remain research limits; no post-test tuning was performed.
