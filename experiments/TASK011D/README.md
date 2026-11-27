# TASK011D — source-only GPU Adapter and dual validation

Preparation only: local synthetic CUDA tests, Route A data admission and two independent frameworks.
No research models, native BA, Pilot or 285 formal jobs ran.

- `uniform_control.py`: source-only GPU math and compact D2H logging.
- `reports/TRANSFER_AUDIT.json` and `PERFORMANCE_PROFILE.json`: measured evidence.
- `data/`: 19 windows and 1216 image/camera admission records, historical exposure explicit.
- `collect_snapshots.py` / `fixed_state_replay.py`: complete A0 inputs and independent A5/A7/A5 branches.
- `run_end_to_end.py`: default validate-only; approved serial independent 285-job path.
- `score_completed_runs.py` / `analyze_results.py`: offline scoring, explicit failure counts, sequence bootstrap.
- `configs/IMPLEMENTATION_LOCK.json`: reviewed code hashes.

Use the existing `D:/aaa/envs/gamecam-vo/python.exe`. Synthetic CUDA is tested on local RTX5060.
Formal native runners are for the approved Linux3090 environment and are gated before model imports.

CPU tests: `python -m unittest discover -s experiments/TASK011D/tests -p test_framework_cpu.py -v`.
CUDA contracts: `python -m unittest discover -s experiments/TASK011D/tests -p test_uniform_cuda.py -v`.
Transfer contracts: `python -m unittest discover -s experiments/TASK011D/tests -p test_no_full_buffer_d2h.py -v`.
Preserve the B/C sibling source trees in this review's reproducibility folder; they are immutable dependencies.

Default safe CLI: `python experiments/TASK011D/run_end_to_end.py`.
FSR default safe CLI: `python experiments/TASK011D/fixed_state_replay.py`.
No approved runtime file is included. Synthetic test fixtures are not experimental outcomes.
