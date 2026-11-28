"""Reuse the previously verified 8GB execution adapter in a new workspace."""
import pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2];TASK=ROOT/'candidate'
old=ROOT.parent/'GameCam-VO-DROID-SPLAT-CANDIDATE/candidate/scripts/run_arm.py'
s=old.read_text()
s=s.replace("['BASE','A5','SCALE','SCALE_A5']","['BASE','A5','ROBUST','ROBUST_A5']")
s=s.replace("source_gate_version=3,algorithm_change='DROID-Splat xy-norm confidence / global support threshold'",
    "source_gate_version=1,algorithm_change='Cauchy IRLS prior; independent eta damping; reweight within both native iterations'")
s=s.replace("TASK/'src/scale_controller.py',\n                TASK/'src/scale_alignment.py',TASK/'src/endpoint_check.py'",
    "TASK/'src/robust_controller.py',TASK/'src/robust_math.py',TASK/'src/gpu_verification.py',TASK/'src/endpoint_check.py'")
s=s.replace("from scale_controller import install,MAIN","from robust_controller import install,MAIN")
s=s.replace("from endpoint_check import check as endpoint_check","from gpu_verification import check as endpoint_check")
s=s.replace('a5_sm120_001/local_a5_splat_c3414af6.so','robust_sm120_001/local_mpsfm_robust_c3414af6.so')
s=s.replace("'local_a5_splat_c3414af6'","'local_mpsfm_robust_c3414af6'")
s=s.replace("extension=load_extension() if a.arm in ['A5','SCALE_A5'] else None","extension=load_extension()")
s=s.replace("scale_enabled=a.arm in ['SCALE','SCALE_A5']","robust_enabled=a.arm in ['ROBUST','ROBUST_A5']")
s=s.replace("a5_enabled=a.arm in ['A5','SCALE_A5']","a5_enabled=a.arm in ['A5','ROBUST_A5']")
s=s.replace("if a.arm=='A5' else None","if a.arm=='BASE' else None")
s=s.replace('Four-arm local exploratory run','MP-SfM-style robust depth-prior local exploratory run')
(TASK/'scripts/run_arm.py').write_text(s)
print('RUNNER_STAGED')
