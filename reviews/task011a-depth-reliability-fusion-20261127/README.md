# TASK011A complete review

Start with FINAL_REVIEW.md and TASK011A_DECISION.json. Current project mainline remains VIPER. MVS is only the explicitly authorized historical auxiliary diagnostic.

All new tables, tests, actual logs, figures, float64 risk/error maps and the exact minimum native prediction fields are included. Raw RGB/EXR GT, model weights, environment binaries and credentials are excluded. Earlier CPU-pass tables/logs are kept; identical array contents are referenced rather than copied twice. Primary evidence remains three reused evaluation frames in one MVS sequence, not a new blind test or VIPER accuracy certificate.

## Standalone mathematical replay

From this extracted directory, with Python, NumPy, SciPy and scikit-learn:

```powershell
python -B code/replay_from_arrays.py --artifact-root .
```

It rechecks the exact saved maps, ranking metrics, mapped probability metrics and regression errors, using frozen error labels and saved calibration parameters. No RGB/EXR, OpenEXR, model, neural training or GPU is needed. This validates the arithmetic, not the independent physical accuracy of the source GT. Original-source reproduction scripts/tests are also supplied; they expect the documented project cache layout and the matching isolated CPU EXR reader.

Original complete ZIP is delivered through the [task Release](https://github.com/Pseven0108/GameCam-VO/releases/tag/task011a-depth-reliability-fusion-20261127); its external SHA file is committed beside the review. The expanded Git review contains the same evidence files. SHA256_MANIFEST.csv covers every member except itself.
