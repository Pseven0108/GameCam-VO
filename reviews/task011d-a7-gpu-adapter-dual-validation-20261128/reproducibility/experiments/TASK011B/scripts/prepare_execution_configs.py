"""Seal arm definitions and unchanged runtime template, without model loading."""
from dataclasses import asdict
import json
from pathlib import Path
import sys

import yaml

from common import TASK,sha,dump

sys.path.insert(0,str(TASK/'CADP_DR_EXPERIMENTAL_BRANCH'))
from controller import arm_config,ARMS


def main():
    frozen=Path('D:/aaa/GameCam-VO/experiments/DROID_W_TASK003_VAL007_OBSERVATION_R1/remote/incoming/native_config.yaml')
    original=yaml.safe_load(frozen.read_text())
    if original['tracking']['uncertainty_params']['gamma_depth']!=.01 or original['tracking']['buffer']!=500:
        raise RuntimeError('Original R2 parameters differ')
    rows=[]
    for arm in ARMS:
        config=asdict(arm_config(arm));dump(TASK/'CADP_DR_CONFIGS'/(arm+'.json'),config)
        rows.append(config)
    dump(TASK/'configs/R2_R3_EXECUTION_PROTOCOL.json',dict(
        status='APPROVED_BUT_GPU_DEVICE_UNAVAILABLE',baseline_commit='c3414af6047d06bafc1a6645d09f23247f3b2cdc',
        project_start_main='7a4d93a8ace18ca37f97949622953ade5b129d86',branch='task011b/validity-aware-cadp-dr',
        GPU_requirement='Allocated RTX3090 24GB; no automatic start/reboot/allocation change',
        windows=20,groups=7,planned_window_runs=140,actual_window_runs=0,
        frames_per_window=64,resolution_hw=[360,640],stride=1,buffer=500,seed=43,
        original_R2_config_sha256=sha(frozen),original_tracking_config=original['tracking'],
        intervention_scope='Frontend main-loop local BA only: predecision and retained updates',
        unchanged=['Initialization and second initialization','U and UBA','Schur solve and post-Schur damping',
                   'Native BA internal iterations','Final BA depth-off path and 7/12 steps','Trajectory filler',
                   'Original model weights','Raw RGB and Camera mapping','Native Metric3D restoration'],
        A0='Installed original DROID-W: already includes Metric3D depth prior',
        A1='Independent candidate s=1 native D=1 endpoint check; not a second distinct depth-enabled algorithm',
        A4_A6='Same validity-aware rank reliability; A6 alone adds genuine prior-free geometry need',
        original_R2_metric_focal='Native predictor uses cfg.cam.fx, not a substituted resized focal; preserve and log actual value',
        initialization_control_identical_across_arms=True,
        risk_is_correctness_probability=False,uniform_attenuation_arm_not_authorized=True,
        runtime_protocol_version='DRAFT_GPU_NATIVE_REGRESSION_UNVERIFIED',arms=rows))
    print('SEVEN_CONFIGS_AND_FROZEN_PROTOCOL_READY_NO_MODEL_RUN',flush=True)


if __name__=='__main__':main()
