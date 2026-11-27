# Primary-source literature review

Scope: 2024–2026 motion/geometry/SLAM methods. Metadata and source identities were checked on2026-11-27. The academic-search MCP tools are absent in this session; the skill's OpenAlex discovery fallback and primary arXiv/CVF/official repositories were used. Search results alone are not evidence of an implemented capability.

## GMOS and GMOS-S

[Paper, arXiv2605.30352v1](https://arxiv.org/html/2605.30352v1), submitted28May2026; [official code](https://github.com/Jyxarthur/gmos). RGB-only proposer fuses frozen Pi3 geometry and SAM2 appearance. Full GMOS propagates object instances; GMOS-S predicts foreground/background motion without the propagator. The paper distinguishes instantaneous motion from sequence-level object membership through MOS-I. This is relevant to parked versus moving vehicles, but those benchmark results do not establish GTA-V accuracy. Our primary candidate is GMOS-S, with raw sigmoid scores retained before image quantization. Five centered context frames include future information; it is an offline prior in these tests.

## GeoMotion, conference versus full release

[Paper, arXiv2602.21810v1](https://arxiv.org/html/2602.21810v1), submitted25February2026; [CVPR primary publication](https://openaccess.thecvf.com/content/CVPR2026/papers/He_GeoMotion_Rethinking_Motion_Segmentation_via_Latent_4D_Geometry_CVPR_2026_paper.pdf); [official code](https://github.com/zjutcvg/GeoMotion). Motion is decoded from Pi3 temporal geometry. The September repository describes a Full variant with recurrent RAFT features, motion/appearance decoupling and optional SAM2 refinement. Those are different configurations, not interchangeable labels for one checkpoint. The inference demo externally normalizes RGB while the model also normalizes it; our direct adapter supplies RGB[0,1] once. This is a documented preprocessing deviation from that demo, not a change to learned parameters. Conference-model and Full-model evidence must be reported separately.

## RoMo

[Paper, arXiv2411.18650v1](https://arxiv.org/abs/2411.18650), submitted27November2024; [official code](https://github.com/google-deepmind/romo). Combines optical flow, robust epipolar geometry and pretrained SAM2 through iterative segmentation. It motivates an independent geometry verifier, because object identity alone is insufficient evidence of current motion. Our RAFT/FB/MAGSAC module is a lightweight independent implementation of this family of geometric tests; it is **not a reproduction of full RoMo or its published scores**. Near-pure rotation, planar scenes and a dominant moving object remain degeneracies.

## DynOSeg

[Paper, arXiv2611.04452v1](https://arxiv.org/html/2611.04452v1), submitted3November2026; [official repository](https://github.com/ACFR-RPG/DynOSeg). It explicitly forms camera-flow residuals using depth and pose, then fuses geometric and semantic encodings. The inspected official commit contains documentation/figures and says implementation is forthcoming. We do not invent a usable checkpoint or claim DynOSeg inference. Its physical residual construction informs our independent depth/pose/flow diagnostics; residual magnitude alone is not motion GT.

## DYNAPO

[Official code and paper link](https://github.com/wuzy2115/DYNAPO). Dynamic-object understanding may support offline annotation, with segmentation propagation and downstream pose/depth/track optimization. The release advertises large VLMs or paid services as options and still lists incomplete demos/evaluators. We do not invoke paid APIs, train a VLM, or treat semantic object descriptions as instantaneous-motion supervision. It is reviewed as a future annotation aid rather than a required dependency of this bounded local study.

## MonST3R

[Paper, arXiv2410.03825v2](https://arxiv.org/abs/2410.03825), submitted4October2024, revised8May2025, ICLR2025; [official code](https://github.com/Junyi42/monst3r). Produces per-time geometry in dynamic scenes and supports downstream video optimization. It is relevant as a separate dynamic geometry reference. It is not an independent physical depth GT, and importing its global optimizer would introduce a large additional inference/optimization pipeline. It is source-reviewed here rather than silently substituted for Metric3D.

## Pi3MOS-SLAM, beyond masks

[Official code](https://github.com/PRBonn/Pi3MOS-SLAM). The inspected frozen Task008 source uses Pi3 local-point z, image confidence and dynamic masks separately. DPVO patch selection uses the dynamic threshold; predicted inverse depth initializes patches and a prior; confidence weights sampled priors; robust depth-scale estimation uses valid patches and geometric variance filtering. These interfaces are not equivalent to multiplying all dense DROID observation weights by a soft mask. A scale-aligned depth experiment therefore needs a separate admission and comparison; depth confidence is neither DROID native U nor a calibrated probability of correct depth.

## Additional existing complementary candidate

BA-Track's MDTracker was already independently executed in TASK009. Its counterfactual static image trajectories can change residual targets, rather than only suppress constraints. We retain this admitted checkpoint as an orthogonal comparison. The local adapter uses predicted Metric3D depth and offline full-window trajectories, so it is not the complete official UniDepth/BA-Track pipeline or a causal online tracker.
