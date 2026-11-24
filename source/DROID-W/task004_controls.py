"""Phase-local policy for the review candidate. No model or tensor imports."""

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import json
import os
from pathlib import Path


SCHEMA = "GAMECAM_TASK004_PHASE_POLICY_V1"
R2_CONFIG_SHA256 = "a213d74874ad953000dde6b7506694b369fad9b2eaccaff58f063accdfbb50fc"
LOCAL_PHASES = frozenset(("frontend_local_predecision", "frontend_local_retained"))
FACTORIAL = dict(E0=(1, 1, 1), E1=(0, 1, 1), E2=(1, 0, 1), E3=(1, 1, 0),
                 E4=(0, 0, 1), E6=(0, 1, 0), E7=(1, 0, 0), E8=(0, 0, 0))
FINAL = dict(F0=0, F1=1, F2=2)


@dataclass(frozen=True)
class Policy:
    arm: str
    local_dwu: tuple
    final_phases: int
    campaign: str


def parse_policy(doc):
    fields = {"schema", "base_config_sha256", "campaign", "arm", "local_dwu", "final_phases"}
    if type(doc) is not dict or set(doc) != fields:
        raise ValueError("Unexpected Task 004 policy fields")
    if doc["schema"] != SCHEMA or doc["base_config_sha256"] != R2_CONFIG_SHA256:
        raise ValueError("Task 004 policy must bind the sealed R2 configuration")
    arm, bits, phases = doc["arm"], doc["local_dwu"], doc["final_phases"]
    if (type(arm) is not str or type(bits) is not list or len(bits) != 3
            or any(type(v) is not int or v not in (0, 1) for v in bits) or type(phases) is not int):
        raise ValueError("Invalid Task 004 factor encoding")
    bits = tuple(bits)
    campaign = doc["campaign"]
    if not ((campaign == "FACTORIAL" and arm in FACTORIAL and bits == FACTORIAL[arm] and phases == 2)
            or (campaign == "E5_FINAL" and arm in FINAL and bits == FACTORIAL["E0"] and phases == FINAL[arm])):
        raise ValueError("Invalid Task 004 arm, factors, or final-BA phase count")
    return Policy(arm, bits, phases, campaign)


@lru_cache(maxsize=1)
def policy():
    path = Path(os.environ["GAMECAM_TASK004_POLICY"])
    if not path.is_absolute():
        raise ValueError("Task 004 policy path must be absolute")
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != os.environ["GAMECAM_TASK004_POLICY_SHA256"]:
        raise ValueError("Task 004 policy hash mismatch")
    return parse_policy(json.loads(raw))


def local_flags(phase, observer_stage, video, motion_only, update_u, use_u):
    if phase is None:
        if observer_stage in LOCAL_PHASES:
            raise ValueError("Observed local BA is missing its explicit Task 004 marker")
        return video.metric_depth_reg, use_u, update_u
    if phase not in LOCAL_PHASES or phase != observer_stage or motion_only:
        raise ValueError("Task 004 local-BA scope mismatch")
    if not (video.metric_depth_reg and use_u and update_u and video.uncertainty_aware
            and video.enable_affine_transform and not video.enable_bidirectional_uncer
            and video.cfg["tracking"]["uncertainty_params"]["gamma_depth"] == 0.01
            and not video.cfg["tracking"]["frontend"]["enable_loop"]):
        raise ValueError("Task 004 vanilla local-BA contract mismatch")
    return tuple(bool(flag) for flag in policy().local_dwu)


def require_approved_runtime():
    if os.environ.get('GAMECAM_NATIVE_CONTROL_BOUNDED')=='1':
        from native_control.stage_authorization import validate_runtime
        return validate_runtime(policy())
    path=Path(os.environ['GAMECAM_TASK004_AUTHORIZATION'])
    raw=path.read_bytes()
    if sha256(raw).hexdigest()!="ce286e8a61947d6ee295341da39d46b227d0160709eaeaa0d6d391b3dc34217c":
        raise SystemExit('Task004B authorization identity mismatch')
    doc=json.loads(raw);root=Path(doc['remote_root']);active=policy()
    seed=int(os.environ['GAMECAM_TASK004B_SEED'])
    attempt=Path(os.environ['GAMECAM_TASK004_ATTEMPT'])
    receipt=json.loads((attempt/'LAUNCH_INTENT.json').read_bytes())
    if (doc['schema']!='GAMECAM_TASK004B_AUTHORIZED_REPEATED_FACTORIAL_V1'
        or seed not in doc['seeds'] or active.campaign!='FACTORIAL'
        or active.arm not in doc['orders'][str(seed)]
        or path!=root/'release/AUTHORIZATION.json'
        or attempt.parent!=root/'results'/('seed'+str(seed))/active.arm
        or receipt['arm']!=active.arm or receipt['seed']!=seed
        or receipt['mode']!='REAL_GPU_CONFIRMATORY'
        or receipt['authorization_sha256']!=sha256(raw).hexdigest()
        or receipt['policy_sha256']!=os.environ['GAMECAM_TASK004_POLICY_SHA256']
        or Path(os.environ['GAMECAM_TASK003_SEALED_CONFIG'])!=root/'release/candidates/r2_sealed_config.yaml'):
        raise SystemExit('Task004B runtime outside approved seed, release or attempt')
    return active
