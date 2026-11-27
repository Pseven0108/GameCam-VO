# Stop boundary and decisions needed

The TASK011C first stage is complete. **Do not start a GPU pilot.** The 300-run
plan cannot be admitted under the supplied source-sequence exclusion rule.

1. Decide how to revise the data protocol. All 47 available Validation sources
   were previously used in comparative full-sequence runs. This is metadata-backed
   exposure, not a claim that their current 64-frame windows are identical. No source
   can honestly be described as historically unused under the present rule.
2. A narrower "not used in TASK011B" exclusion alone still leaves only three Rain
   sources. It cannot retain the current four-per-weather requirement. Reusing old
   windows, changing to Train, changing counts, or downloading data is not automatic.
3. Review same-state mean matching versus a stronger cross-run fixed-state estimand.
   Actual keyframe/source histories can diverge. The current A7 definition matches
   the former only, without changing the frozen frontend schedule.
4. Resolve numeric secondary-outcome acceptability margins before confirmatory GPU
   results; do not derive margins after looking at those outcomes.

After those decisions, and only with explicit subsequent GPU admission, the next
engineering checks are actual native-grid A7 mean/support checks on CUDA, unchanged
A0/A1 endpoint regression and a frozen-protocol technical pilot. No extra model,
confidence calibration, Geometry Need, BA rewrite or new algorithm stage is proposed.

This review neither promotes A5 nor establishes that uniform attenuation suffices.
Its sole permitted research decision is INCONCLUSIVE.
