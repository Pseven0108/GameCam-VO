"""Explicit TASK011E runtime grant; secondary proposals remain UNAPPROVED."""
import csv,json
from pathlib import Path
from task011e_io import TASK,sha

ALLOWED=('PRIOR_CACHE','END_TO_END')

def verify_requested_job(action,key,window,arm=None,seed=None):
    if action not in ALLOWED:raise PermissionError('Action not authorized by TASK011E')
    if action=='PRIOR_CACHE':
        windows=json.loads((TASK/'configs/GPU_RGB_INPUTS.json').read_text())['windows']
        if window not in {w['window_id'] for w in windows} or key!='cache_'+window:raise PermissionError('Cache window/job key mismatch')
        return
    rows=list(csv.DictReader((TASK/'configs/EXECUTION_ORDER.csv').open()))
    matches=[r for r in rows if r['job_key']==key]
    if len(matches)!=1 or (matches[0]['window'],matches[0]['arm'],int(matches[0]['seed']))!=(window,arm,seed):
        raise PermissionError('Requested window/arm/seed differs from authorized frozen job')

def verify_model_weights():
    identity=json.loads((TASK/'MODEL_WEIGHT_IDENTITY.json').read_text())
    if identity.get('status')!='VERIFIED_EXISTING_WEIGHTS':raise PermissionError('Model identity incomplete')
    for r in identity['weights']:
        p=Path(r['path'])
        if not p.is_file() or p.stat().st_size!=r['bytes'] or sha(p)!=r['sha256']:
            raise PermissionError('Actual model weight changed: '+r['name'])

def require_approved_runtime(path,action,job_key):
    if not path:raise PermissionError('Formal GPU execution not authorized in this preparation stage')
    p=Path(path)
    if not p.is_file():raise PermissionError('Explicit user authorization file required')
    x=json.loads(p.read_text())
    required=(x.get('stage')=='TASK011E_FAST_285_CONTINUATION_R2',x.get('approved') is True,
        x.get('secondary_thresholds_approved') is False,
        not x.get('approved_secondary_thresholds'),
        x.get('secondary_proposals_sha256')==sha(TASK/'reports/SECONDARY_THRESHOLD_PROPOSALS.csv'),
        bool(x.get('user_authorization_reference')),not x.get('test_only',False),
        x.get('user_authorization_sha256')==sha(TASK/'intake/USER_AUTHORIZATION.txt'),
        x.get('continuation_authorization_sha256')==sha(TASK/'intake/CONTINUATION_AUTHORIZATION.txt'),
        x.get('cache_continuation_state_sha256')==sha(TASK/'configs/CACHE_CONTINUATION_STATE.json'),
        x.get('protocol_sha256')==sha(TASK/'configs/FROZEN_EXPERIMENT_PROTOCOL.json'),
        set(x.get('allowed_actions',[]))==set(ALLOWED),action in ALLOWED,
        job_key in x.get('approved_job_keys',[]),
        x.get('model_weight_identity_sha256')==sha(TASK/'MODEL_WEIGHT_IDENTITY.json'))
    if not all(required):raise PermissionError('Explicit TASK011E scope/hash/job binding mismatch')
    protocol=json.loads((TASK/'configs/FROZEN_EXPERIMENT_PROTOCOL.json').read_text())
    for r in protocol['files']:
        if sha(TASK/r['path'])!=r['sha256']:raise PermissionError('Frozen configuration changed')
    implementation=json.loads((TASK/'configs/IMPLEMENTATION_LOCK.json').read_text())
    for r in implementation['files']:
        if sha(TASK/r['path'])!=r['sha256']:raise PermissionError('Reviewed implementation changed')
    verify_model_weights()
    return x
