# Actual failure context and intervention exposure

All140 planned outcomes are retained. 42 lack a complete64-frame trajectory; 42 failed before any controlled BA was logged. No accuracy is imputed.

Frozen native warmup is12 accepted keyframes. The original observer guard preserves a partial uninitialized state instead of fabricating a full trajectory. No warmup, frame count, selection or algorithm parameter was adjusted after observing failures.

| Window | Environment | Complete /7 | Pre-control failures | All7 init failures | Accepted KF range |
|---|---|---:|---:|---|---|
| val_001_00207-00270 | Day | 7 | 0 | False | 61–61 |
| val_002_00244-00307 | Day | 7 | 0 | False | 62–62 |
| val_003_00135-00198 | Day | 7 | 0 | False | 47–47 |
| val_004_00193-00256 | Day | 7 | 0 | False | 34–34 |
| val_005_00809-00872 | Night | 7 | 0 | False | 14–19 |
| val_006_00077-00140 | Night | 7 | 0 | False | 12–12 |
| val_007_00212-00275 | Night | 7 | 0 | False | 34–43 |
| val_008_01384-01447 | Sunset | 0 | 7 | True | 1–1 |
| val_009_00214-00277 | Sunset | 0 | 7 | True | 1–1 |
| val_010_00662-00725 | Sunset | 0 | 7 | True | 7–7 |
| val_011_00723-00786 | Sunset | 0 | 7 | True | 1–1 |
| val_018_00324-00387 | Rain | 0 | 7 | True | 9–9 |
| val_019_00202-00265 | Rain | 7 | 0 | False | 29–30 |
| val_020_00298-00361 | Rain | 7 | 0 | False | 14–15 |
| val_021_00677-00740 | Snow | 0 | 7 | True | 1–1 |
| val_022_00442-00505 | Snow | 7 | 0 | False | 15–15 |
| val_023_00416-00479 | Snow | 7 | 0 | False | 32–33 |
| val_024_00410-00473 | Snow | 7 | 0 | False | 12–12 |
| val_033_00427-00490 | Night | 7 | 0 | False | 14–14 |
| val_037_00441-00504 | Rain | 7 | 0 | False | 14–14 |

An entire seven-arm set failing before controlled Local BA cannot support a claim that CADP-DR improved or damaged tracking. Such cases still count against the planned-window completion rate. Their image files need not be duplicates, and insufficient accepted motion is not proof of frozen RGB.

The accepted-keyframe count at exit and actual logged BA exposure are observations. They do not establish the physical cause of initialization failure or predict whether a longer sequence would succeed. No replacement or longer-window experiment was run.
