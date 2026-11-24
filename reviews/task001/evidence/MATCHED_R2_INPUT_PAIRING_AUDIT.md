# Input pairing

Exact pairing was verified for the 92 frozen segments at 640x360, stride=1. For each segment the audit checked the original JPEG file bytes,
the archived OpenCV 4.8.1 resize/remap, the effective float32 K, and the historical RGB float32 tensor hash.
Each actual run rechecked its lossless BGR receipt for both tracking and trajectory filling. The two native loaders may normalize tensors differently after ingest.
The variable-K virtual camera branch only uses the frozen remap; the first-person dataset or the older stride=4 run is outside this analysis.

No GT pose was supplied to the GPU program. The already approved camera calibration/remap is part of the common input. Pose GT is accessed on the local PC
for scoring via RGB ID minus 1, using the frozen historical hashes. Frame-number mapping is verified; a separate physical-clock validation is not claimed.
