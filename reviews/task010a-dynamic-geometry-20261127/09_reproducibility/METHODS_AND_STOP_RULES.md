# Prespecified implementation and stopping rules

All native comparisons retain the same pretrained tracker, native U/UBA, depth-prior strength, initialization, Final BA and Filler within the TASK009-derived local protocol. No production source or original checkpoint is edited.

| Method | Isolated intervention |
|---|---|
| baseline | No external target/weight hook |
| legacy | Historical two-end Pi3MOS soft gate, floor0.1 |
| legacy_mean | Uniform weight multiplier with exactly the same current-call mean as legacy; controls spatial pattern versus total geometric strength |
| neutral | Max-end Pi3MOS score, exact neutral region≤0.4, linear decay to floor0.25 at0.8 |
| gmos | Same neutral gate using GMOS-S scores |
| geomotion | Same neutral gate using conference GeoMotion scores |
| geometry | Official RAFT/FB/MAGSAC residual gate on admitted lag2/4 edges; missing/degenerate evidence is neutral |
| fusion | GMOS neutral evidence AND independent geometry, attenuated according to remaining native source-UBA support |
| static | Frozen MDTracker counterfactual static-target blending, no weight change |
| fusion_static | Static-target blend followed by the fusion weight gate |
| depth | Separate one-scale-per-window Pi3MOS/Metric3D inverse-depth blend; no dynamic weight hook |
| depth_static | Depth candidate plus independently frozen static-target module |
| depth_fusion | Depth candidate plus GMOS/geometry/U-complement gate |

Depth admission uses only predicted fields: finite positive depths, at least1024static-support pixels/frame, and temporal scaleP95/P05≤2. One global scale anchors Pi3 to Metric3D prediction units. Eligible per-pixel ratios are0.5–2; blend fraction0.25. These are explicit exploratory design choices, not GT-derived/calibrated thresholds. No network-confidence score is treated as a depth-error probability. An admitted candidate may be evaluated for VO utility without claiming its pixel depths became more accurate.

Development uses seeds43,44,45, serially, with reversed/interleaved method order. The initial baseline `s43_r1` predates the final stage/projection observer and remains in the master table as a preliminary compatibility run. Before seeing any candidate trajectory score, `s43_r2` is designated the matched observer-version baseline. Do not replace it after scoring. Native floating-point reproducibility is not assumed.

Transfer candidates/parameters must be frozen after development and before computing held-out trajectory metrics. No held-out sequence is dropped for poor performance. Real and game error units are reported separately. Within-window seeds are repeated runs, not independent scene samples.

Model-specific failures are preserved and diagnosed before a uniquely named new software attempt. Stop escalating a candidate if official code/weight identity or finite outputs cannot be established. No claim of full RoMo/DynOSeg/DYNAPO/MonST3R reproduction is permitted from the lightweight verifier. Full GeoMotion, if executed, must be identified separately from the conference model and optional SAM2 refinement.

Stop the research iteration after predeclared transfer has resolved whether the candidate's development gain persists. A method that improves one Night window but harms other environments is not accepted as a generalized improvement. Further post-test tuning would require a new development protocol and is not performed merely to turn this table into PASS.
