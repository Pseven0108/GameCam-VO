# Input amendment before any comparative trajectory score

The initially frozen Train Day001 RGB309–372 window failed native initialization:
64 frames retained only its first keyframe. The independent offline camera audit
found a total annotated path of 4.580851103807634e-08 game units and a maximum
pose-matrix change of 8.695081987752928e-09. This is effectively stationary.
No candidate trajectory or comparative accuracy was computed on this window.

Use the previously established moving Train Day004 RGB1658–1721 window instead,
with Camera1657–1720, for **all four arms**. This is the historical 64-frame GPU
smoke input, selected for initialization viability, without tuning to candidate
ATE/RPE outcomes. Keep the same seed, 640×360, stride1, buffer96 and algorithm
parameters. Recompute all common priors for the new exact RGBs.

Preserve the initial protocol, Day001 data/cache, failed BASE_001 logs and
ALGORITHM_FAILURE.json. The new BASE run has a distinct attempt ID. The original
LOCAL_PROTOCOL.json remains a historical V1; this amendment defines the V2 input.
No remote state is read or modified.
