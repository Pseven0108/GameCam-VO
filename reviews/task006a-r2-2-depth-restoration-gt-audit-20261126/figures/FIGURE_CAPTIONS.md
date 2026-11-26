# R2.2 figure captions and integrity notes

All plots use actual archived inference or current CPU-audit results. No new model inference.
Sequence0001 was observed in R2.1. Three frames are technical samples, not three independent sequences. No CI, significance or meter claim.

1. **MVS_SPATIAL_ERROR_CONFIDENCE**: rows0001/0000,0049,0099. Native RGB unchanged; GT and prediction display70–2000 native units on a log scale, invalid GT gray. Prediction uses bilinear with the legacy focal factor and one Calibration0000 scale. AbsRel colorbar is display-limited0–1; confidence0.85–1 is a raw-score display range, not a probability. Original arrays and statistics are never display-clipped. Source:pixel_maps, PAIRED_DEPTH_ERROR_METRICS.csv, original RGB/GT SHA index.
2. **ZERO_PIXEL_RESTORATION_DETAIL**: all seven historical zero coordinates are overlaid on the full RGB. Lower row is an explicitly labeled crop x638:724,y145:207. Depth display0–25 uses the same scale in both compared images. Repaired pixels can retain prediction error. Source:ORIGINAL_SEVEN_ZERO_PIXELS.csv and raw/restored arrays.
3. **PAIRED_ERROR_AND_SEVERE**: paired per-frame mean AbsRel and percent with error≥1.0 for three already-observed frames. Same finite-positive GT masks, per-variant calibration-only global scale. Lines connect the same image, not independent replicate experiments. Source:PAIRED_DEPTH_ERROR_METRICS.csv.
4. **CONFIDENCE_ERROR_DIAGNOSTICS**: mean error and severe-error frequency in bins with boundaries derived only from Calibration0000. Bin1 is lowest raw confidence, bin10 highest. This is a descriptive score-error plot, not a calibration reliability diagram. Source:CONFIDENCE_ERROR_BINS.csv.
5. **GEOMETRY_ALIGNMENT_UNIT_AMBIGUITY**:198 adjacent-pair medians and pose-only largest-translation controls. Panelc rescales only GT depth, keeping native translations fixed; it checks consistency of those numbers. Scaling depth and translation together leaves projection invariant, so no panel establishes meters. Source:ALL_198_ADJACENT_Z_DEPTH_PAIRS.csv and MAX_TRANSLATION_ALIGNMENT_CONTROLS.csv.

Exports:Python matplotlib only, PNG220dpi, editable-label SVG, embedded-raster PDF. Pseudocolor and crops are documented above. RGB/GT input files are excluded from public package; derived figures and prediction/error arrays are included.
