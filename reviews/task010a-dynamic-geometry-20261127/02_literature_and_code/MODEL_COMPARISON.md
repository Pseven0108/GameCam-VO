# Candidate selection rationale

| Candidate | Motion evidence | Independent model interface | Decision |
|---|---|---|---|
| Pi3MOS | Temporal geometry plus learned dynamic head | RGB video → dynamic score, local points, confidence, pose | Historical Night cache retained; independent new smoke and transfer considered |
| GMOS-S | Pi3 temporal geometry + SAM2 features | Five RGB frames → one foreground logit map | Priority1, official learned weights; current outputs saved as float arrays |
| GeoMotion CVPR | Pi3 geometry plus flow magnitude adapter in current code | RGB temporal tensor + flow → motion map, local points, raw motion logits | Priority2; distinguish code/weight compatibility and preprocessing from mask quality |
| Full GeoMotion | Recurrent RAFT features, MAD training, optional SAM2 | Separate model class/checkpoint/evaluator | Source audit; run only if conference interface and local resources justify expansion |
| RoMo | Flow + epipolar cues + iterative SAM2 | Sequence-level pipeline | Independent geometric verifier implemented; full RoMo not claimed |
| DynOSeg | Depth + pose + observed flow + semantic encoding | Not released at inspected commit | Not runnable; no invented result |
| DYNAPO | VLM semantics + video segmentation propagation | Large/offline multistage pipeline | Not selected for local online gate; no paid API |
| MonST3R | Dynamic pointmaps and joint optimization | Pair/video geometry | Reference only; no metric-GT substitution |
| MDTracker | Counterfactual static image trajectories | RGBD video + point queries | Complementary static-target ablation, original admitted parameters |

Model ranking will be based on measured DROID-W transfer and actual resource use. Motion-mask area and visual plausibility are not detection accuracy. No benchmark score from a paper is transferred to this experiment.
