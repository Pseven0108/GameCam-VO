# R0: actual TTA validity audit

16 unchanged original NPZ caches: VIPER10 images/five weather groups plus six historical auxiliary MVS images. No model forward.

The historical ungated relative maximum is **81369773.86474609**. This is a diagnostic over finite raw depths including zeros, not an input to the new controller. Even valid positive pairs can have a large asymmetric T1; T2=abs(a-b)/(abs(a)+abs(b)+1e-6) is bounded below1 for positive pairs. T3=abs(log(a+1e-6)-log(b+1e-6)) is a log-scale quantity, not a bounded relative quantity. T4 retains native depth units.

The preregistered numerical lower bound1e-6 is in output units, not1micrometre or an independently measured distance. Native/Flip validity require finite values above that bound. Pair validity also requires the original boolean tta_valid. On10 VIPER images there are **94 invalid Native pixels** and **86 Native-valid/TTA-invalid pixels**.

Every undefined disagreement remains NaN with an explicit mask. No invalid pair is replaced by a zero disagreement. Invalid Native never receives a nonzero prior coefficient in controlled arms. Native-valid/TTA-invalid pixels use Native-only fallback in runtime TTA controls. The original depth arrays, original saved NaNs, restoration method and all original NPZ files remain unchanged.

The strict historical GT gate still fails. The seven zero Native predictions on validGT in MVS0001/0099 are included with AbsRel1 in the full-GT secondary diagnostic; they are not deleted to improve a score.

See TTA_VALIDITY_AUDIT.csv, TTA_DISAGREEMENT_COMPARISON.csv, TTA_NUMERICAL_STATISTICS.csv and SOURCE_FIELD_PROVENANCE.md. Bin-grid entropy/statistics are audited, not silently resized into or substituted for final-depth reliability.
