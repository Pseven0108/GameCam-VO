# TASK011C — CPU readiness and data admission

This is an independent first-stage implementation based on reviewed commit
`78ca580c636bb232eba6d46ccf704b193988b5ab`. No SLAM or GPU experiments were run.

Current outcome: **CPU_PASS / DATA_BLOCKED / INCONCLUSIVE**.
All 47 VIPER Validation sources already participated in historical comparative
experiments; none meets the required source-sequence exclusion rule. Even
excluding only TASK011B, Rain has three remaining sources, below the required four.

`uniform_control.py` delegates A0/A1/A4/A5 unchanged to TASK011B and implements
A7 at the actual BA source/mask/sampling grid. Means are matched against the
counterfactual A5 field on the **same** input state, not falsely claimed equal
across diverging independent trajectories. It never calls a depth model.

On the user's Windows workspace, use the existing environment, with CPU-only
visibility and D: temporary storage:

```powershell
$env:CUDA_VISIBLE_DEVICES = '-1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:TEMP = 'D:\aaa\tmp\gamecam-vo'
$env:TMP = $env:TEMP
D:\aaa\envs\gamecam-vo\python.exe -B experiments/TASK011C/run_cpu_tests.py --attempt reviewer_cpu_001
```

The 56 A7 tests are also independently runnable with `unittest discover` in
`experiments/TASK011C/tests`. They require NumPy, SciPy and CPU PyTorch. The
66 exact inherited regressions use fixed historical metric and native-regression
fixtures; `run_cpu_tests.py` materializes those two unchanged files from the parent
Git commit. Their historical trajectory-metric tests additionally require the
existing `VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/pipeline`.
This environmental requirement is retained rather than rewriting their tests.

The data audit uses only existing metadata, ZIP central directories and offline
camera caches. Its output directory is immutable per completed audit. It does
not extract or decode RGB. No formal window/run-order manifest is frozen.

Do not invoke historical TASK011B GPU launchers as TASK011C. This delivery has
no GPU runtime runner or ready-to-execute 300-run schedule. A new sampling
decision and subsequent explicit GPU admission are required.
