# TASK011C preregistered first-stage protocol

Date: 2026-11-28, Asia/Shanghai. Parent: `78ca580c636bb232eba6d46ccf704b193988b5ab`.
Branch: `task011c-maxfusion-spatial-utility-20261128`.

The current delivery ends after data audit, A7 implementation and CPU validation.
It does not authorize a pilot or any of the prospective 300 GPU runs.

## Research contrast

Determine whether A5's spatial allocation adds utility beyond an equally strong
uniform prior. Arms: A0 installed original, A1 isolated D1 endpoint, A4 validity-aware
rank fusion, A5 validity-aware max fusion, A7 uniform attenuation. A1 is an
implementation endpoint control. A6/Geometry Need and new depth models are absent.

All existing A0/A1/A4/A5 functions and native candidate sources are byte-preserved
from the parent. Alpha is 0.01. U/UBA, target weights, native Schur/retraction,
initialization, final BA and filler retain their approved paths. Only Frontend
Main-loop Local BA may receive A7's appended prior-strength tensor.

## Data eligibility, before algorithms

- Validation only; 20 distinct source sequences, four each Day/Sunset/Rain/Snow/Night.
- Exclude TASK011B's 20 sources AND every source used in earlier comparative runs.
  Past stride=4 results remain historical exposure even though stride=1 is now active.
- Deterministic midpoint of 64 consecutive valid original RGB frames; no replacement
  by an algorithm outcome. Input 640x360, stride=1, original intrinsics mapping.
- Window K maximum deviation <0.001 px; exact camera ID = RGB ID - 1.
- GT path length >0.0001 native camera units, fixed before selection. No new metre claim.
- If any weather has fewer than four eligible sources, stop before GPU and do not
  relax the exclusion, weather balance, split or motion threshold.

No formal source set could be frozen in this stage: eligible source count is zero.
Candidate midpoints in the audit are census diagnostics, not selected windows.

## Prospective execution, currently NOT RELEASED

Three seeds 43/44/45, five arms, one fresh initialization per arm/window/seed.
Buffer 500, 64 frames, 640x360, stride=1, frozen R2/weights, existing native
MotionFilter preprocessing/autocast. A precomputed order is required only after
a valid source manifest exists. No schedule was invented for nonexistent windows.
Pilot outcomes, if later approved, must stay in the final sample.

## Prospective inference

Primary contrast: sequence-level paired A5 minus A7 Sim3 ATE/path (%). Negative
favours A5. Three seeds are within-sequence repeats, never independent sources.
Take the within-source paired mean across jointly scorable seeds; retain/report
the count and identities of common seeds. Then bootstrap source IDs with replacement
10,000 times, carrying that source's repeats together. Also report the stricter
all-three-seeds jointly-scorable subset as sensitivity, not silently substitute it.
Bootstrap Monte Carlo seed must be frozen before first GPU result.

Do not impute error zero for failed/unscorable runs. Report planned, complete,
initialized and ATE-scorable denominators separately by arm/weather/seed. Compare
paired completion indicators on all planned runs, alongside conditional error
on common scorable runs. Survivor effects limit interpretation.

Secondary: Sim3 RMSE, SE3 ATE/path, translation/rotation RPE, raw path ratio error,
runtime and peak VRAM. Native units and scale-aligned shape are distinct. No metric
scale recovery claim follows from Sim3 ATE. Other arm comparisons are secondary.

PROMOTE_A5 additionally requires a negative primary CI upper bound, no completion
disadvantage exceeding five percentage points, and acceptable secondary outcomes.
The task's phrase "unacceptable deterioration" is not a numeric margin; numerical
runtime/RPE/raw-scale margins require preregistration before future confirmatory
results are inspected. Crossing zero is inconclusive, not equivalence.

No bootstrap or hypothesis test was computed on synthetic CPU data or on borrowed
TASK011B scores. Current research decision: INCONCLUSIVE.
