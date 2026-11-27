# Actual independent interfaces and semantics

| Model | Input used | Saved map | Auxiliary meaning | Integration |
|---|---|---|---|---|
| Pi3MOS | RGB[0,1], three causal-within-window frames[t−10,t−5,t], clipped boundary context;255000pixel cap | Original sigmoid dynamic score | `confidence`=uncalibrated geometry/depth score; `depth`=local-point z, nonmetric | Legacy/neutral observation gates; separately scale-aligned depth candidate |
| GMOS-S | RGB five centered frames[t−8,t−4,t,t+4,t+8]; Pi3→CPU cache, SAM21024square encoder, original fusion head | Sigmoid foreground logit, float32 before PNG quantization | Frame confidence head exists but is not a depth probability and is not used in BA | Neutral gate or geometry-verified gate |
| GeoMotionCVPR | RGB[0,1] four-frame chunks,255000pixel cap; model performs ImageNet normalization internally; independent RAFT magnitude | Original `motion_mask` | Saved generic `confidence` field is **raw motion-decoder logits**, not depth confidence; `depth` is relative local-point z | Separate neutral gate; not a confidence-weighted depth replacement |
| FullGeoMotion | Separate official checkpoint and recurrent RAFT128channel features; actual execution status in its receipts | Raw detector, optional SAM refinement separately named | Same distinction between raw motion logits and depth confidence | Only claim native integration if a distinct Full-method run exists |
| MDTracker | RGBD[1,32,4,H,W], pretrained frozen tracker, predicted Metric3D depth,100point queries | Total image tracks, counterfactual static image/depth tracks, visibility and motion score | `static_xyz` contains image x/y plus predicted depth, not Euclidean XYZ | 2D static-target blend, not new3D observations |

All arrays are float outputs with original frame-ID/context metadata; `PREDICTION_SHA256.json` seals admitted caches. Original model code, checkpoints and baseline packages are not overwritten. Direct adapters strictly load all required parameters; the single documented unused GMOS checkpoint positional buffer is the only omitted key.

Spatial mapping is explicit per axis: source pixels→model resize using half-pixel centers; native feature positions correspond to tracker pixels8x,8y.14pixel model-size rounding can slightly change the real4:3aspect ratio; actual dimensions are in every receipt. There is no crop. Model image sizes and temporal receptive fields are not falsely declared identical.

The new Windows venv and raw model-loading failures remain recorded. Successful independent GPU forwards use the existing gamecam-vo environment. Local native DROID-W runs use the existing isolated WSL torch2.7.1/CUDA12.8 extension; they are not numerically certified equivalent to the remote CUDA11.8 production build.
