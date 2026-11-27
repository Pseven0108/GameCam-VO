# Official source identity and executable-scope audit

Retrieved source archives are outside the research repository. The exact commits and downloaded archive identities below are retained without vendoring external model source/weights into the review. No default branch or historical source was replaced.

| Project | Official commit | Retrieved status | Root license metadata |
|---|---|---|---|
| [Jyxarthur/gmos](https://github.com/Jyxarthur/gmos/tree/24112848a118936c959871b6cc3d47c51287c30b) | 24112848a118936c959871b6cc3d47c51287c30b | SOURCE_AVAILABLE | Apache-2.0 |
| [zjutcvg/GeoMotion](https://github.com/zjutcvg/GeoMotion/tree/306aad2e04ef0e96aefac3ef1967b007eacb2cf1) | 306aad2e04ef0e96aefac3ef1967b007eacb2cf1 | SOURCE_AVAILABLE | MIT |
| [google-deepmind/romo](https://github.com/google-deepmind/romo/tree/86af30b55bc159a80847adb155fb0d70b5b57a53) | 86af30b55bc159a80847adb155fb0d70b5b57a53 | SOURCE_AVAILABLE | Apache-2.0 |
| [ACFR-RPG/DynOSeg](https://github.com/ACFR-RPG/DynOSeg/tree/9d946c704f74f7b8afe34f4c113a2d4e13b4b288) | 9d946c704f74f7b8afe34f4c113a2d4e13b4b288 | SOURCE_AVAILABLE | BSD-3-Clause |
| [wuzy2115/DYNAPO](https://github.com/wuzy2115/DYNAPO/tree/11d31346c23b2fd53f2178ce5e650a6ffbf0bb7f) | 11d31346c23b2fd53f2178ce5e650a6ffbf0bb7f | SOURCE_AVAILABLE | None |
| [junyi42/monst3r](https://github.com/junyi42/monst3r/tree/574cc77ad278bad582f470e5382624e01f8769a7) | 574cc77ad278bad582f470e5382624e01f8769a7 | SOURCE_AVAILABLE | NOASSERTION |
| yyfz233/Pi3 | UNAVAILABLE | SOURCE_FETCH_FAILED | NOT_ESTABLISHED |
| [facebookresearch/sam2](https://github.com/facebookresearch/sam2/tree/2b90b9f5ceec907a1c18123530e92e794ad901a4) | 2b90b9f5ceec907a1c18123530e92e794ad901a4 | SOURCE_AVAILABLE | Apache-2.0 |

## Actual interfaces and exclusions

- GMOS: `core/pi3_encoder.py`, `core/sam2_encoder.py`, `core/gmos_s.py`; independent official GMOS-S forward, CPU offloading between encoders. The full instance propagator is not executed.
- Conference GeoMotion: direct Pi3 motion detector in the inspected source, explicit RGB[0,1] and recorded flow magnitude. The standalone demo has an additional normalization path; our adapter avoids double ImageNet normalization.
- Full GeoMotion: `motion_seg_inference_raft.py` helpers and `pi3/models/pi3_conf_flow_cam_lowfeature_wo_mean_raft.py`; independent official raw detector, recurrent RAFT hidden features checked against a native torchvision forward hook. Optional SAM2 post-refinement is not part of this detector test. Actual completion/resource outcome is in the final report, not inferred from this source audit.
- Pi3MOS: reused fixed TASK008 model source and official checkpoint, independent `Pi3.forward` only. It produces motion probability, raw confidence, local points and pose. It does not launch DPVO or Pi3MOS-SLAM BA. The checkpoint/source identities and strict-load receipt accompany each new model run.
- The original Pi3 GitHub location returned404; the admitted GMOS source contains the encoder implementation needed for GMOS-S. This is not a claim of a successful fresh clone of that unavailable URL.
- RoMo: official geometry/SAM2 implementation inspected; the task-specific RAFT/FB/MAGSAC verifier is independent and not a reproduction of the full RoMo pipeline.
- DynOSeg: inspected release states code is forthcoming. No runnable model/weight is fabricated.
- DYNAPO and MonST3R: source/reference audit only; no paid VLM service, global optimization or inferred benchmark scores.
- BA-Track MDTracker: previously admitted tensor-only checkpoint and unmodified source; an independent static-target comparison, with predicted Metric3D depth rather than the complete published UniDepth pipeline.

## Production protection

The native runner imports frozen DROID-W frontend, DepthVideo, Backend and Filler classes from the preserved TASK009 compatibility workspace. New hooks and runners live only under TASK010-A. The Windows and WSL model runtimes differ and are not advertised as the formal remote3090 baseline. Runtime receipts identify actual extension and tracker checkpoint hashes; `ORIGINAL_ASSET_PROTECTION.json` performs the final historical read-only hash check.

The fresh worktree branch starts at sealed TASK009 commit `ff0c9ed761dbcdd6d2fe7b2cda5651c6e173efe1`. The historical dirty worktree, its index, branches and all source/experimental artifacts remain untouched. Publication uses a new commit/branch and an isolated index; repository visibility and default branch are preserved.
