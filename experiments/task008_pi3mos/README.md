# TASK008 Pi3MOS Independent Inference

Frozen official Pi3MOS source remains outside GameCam-VO. See configs/night007_safetensors.json and reports/TASK008_REPORT.md.
Use the independent pi3mos-infer environment. The completed adapter is scripts/infer_pi3mos_safetensors.py; initial infer_pi3mos.py is preserved as the failed pre-forward format attempt, not a second valid pipeline.
No DPVO extension/setup.py, no DROID-W modification, no BA integration. Only approved Night007 A/B inputs. Full float32 outputs are retained privately, excluded from Git.
Review directory: reviews/task008-pi3mos-night007-independent-inference-20261126.
