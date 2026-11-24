"""Additional narrow Task004C stage grant; the original factorial gate is retained."""
import hashlib,json,os
from pathlib import Path
from control_common import ControlError
from native_control.stages import mode_spec

AUTH_SHA='f4282963f20982c1ae0a17606d3494cd99f940c148b611755adafc6f110b4714'

def validate_runtime(active):
    root=Path(os.environ['GAMECAM_NATIVE_WORKSPACE']).resolve()
    if root!=Path(__file__).resolve().parents[2]:raise ControlError('Stage workspace mismatch')
    auth=root/'authorization/TASK_REQUEST.txt'
    if hashlib.sha256(auth.read_bytes()).hexdigest()!=AUTH_SHA:raise ControlError('Stage authorization identity mismatch')
    token=json.loads((root/'evidence/CPU_STAGE_RELEASE.json').read_text())
    mode=os.environ['GAMECAM_NATIVE_APPROVED_MODE'];spec=mode_spec(mode)
    out=root/'attempts'/mode
    intent=json.loads((out/'LAUNCH_INTENT.json').read_text())
    if (intent['spec']!=spec or intent['source_commit']!=token['candidate_commit']
        or os.environ.get('GAMECAM_NATIVE_INTERNAL_CHILD')!=intent['child_token']
        or os.environ.get('GAMECAM_NATIVE_SOURCE_COMMIT')!=token['candidate_commit']
        or Path(os.environ['GAMECAM_NATIVE_ATTEMPT'])!=out
        or active.arm!='E0' or active.campaign!='FACTORIAL' or active.local_dwu!=(1,1,1)
        or active.final_phases!=2):
        raise ControlError('Stage runtime is outside its frozen grant')
    return active
