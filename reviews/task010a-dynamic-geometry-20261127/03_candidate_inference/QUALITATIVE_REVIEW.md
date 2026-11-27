# Qualitative observations from actual output contact sheets

Reviewed actual RGB-aligned outputs on 2026-11-27; no moving-object annotations exist. The fixed sampled rows are window indices4,16,28, not rows selected for a favourable mask. These are visual observations, not measured precision, recall or static false-positive rates.

| Window / frame | Observed behaviour | Limit |
|---|---|---|
| Day004 /1662 | Pi3MOS and conference GeoMotion mark the nearer left car; GMOS-S largely does not, while marking vehicles ahead. | A still overlay cannot establish whether that car is moving in world coordinates. Relative mask disagreement is established; recall is not. |
| Night008 /1282,1294,1306 | All three identify the car ahead. Conference GeoMotion also marks a large right roadside region in the first row. | Roadside spillover is a qualitative concern; no pixel GT supports a numeric false-positive score. |
| Rain030 /328 | Conference GeoMotion covers much of the building facade; GMOS-S has very little support, while Pi3MOS marks parts of the car body/hood. | Static-building coverage is suspicious under camera rotation. The camera-attached hood is moving relative to the world, so marking it is **not automatically a false positive**. |
| Rain030 /340,352 | GMOS-S and conference GeoMotion focus on the visible vehicle; Pi3MOS retains broader support on the camera vehicle. | Different learned definitions of moving objects and ego-car regions may affect VO; correspondence utility must be measured separately. |
| Snow032 /649,661,673 | All three cover the truck. GMOS-S/GeoMotion emphasize additional cars or the pedestrian in later rows. Pi3MOS has more spread on some buildings/car-body regions. | Does not establish instantaneous-motion classification of every object. |
| Downtown1 /605,617,629 | All models cover several pedestrians. Some also cover the van/background vehicle; GMOS-S marks more of the close pedestrian at617. | A parked-versus-moving-van label is not inferred from one still image. Camera motion and object tracking need independent annotations. |
| WildWorld third-person /68,80,92 | All three follow much of the central game character despite vegetation and low light; shape and score extent differ. | This is game footage, qualitative only. K and camera/motion GT are not admitted, so no SLAM accuracy is reported for this window. |

The conference model uses four-frame chunks and GMOS-S uses centered five-frame context; boundary and temporal-context effects are possible. The measured flow-warp proxy reports discontinuities but cannot identify which model is correct. A low dynamic fraction or high empty-mask agreement is not evidence of superior segmentation.

Specific unsupported cases remain: labelled pure rotation, verified stopped NPCs/parked cars, small-object recall, and reflection/shadow confusion rates. The present task does not manufacture those labels. Reviewers should use full raw float outputs and the saved context IDs, not the contact sheets alone.
