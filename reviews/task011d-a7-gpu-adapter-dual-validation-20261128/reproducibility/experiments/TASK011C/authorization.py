"""Fail-closed gate. This preparation stage produces NO approved runtime file."""
import csv,json
from pathlib import Path
from common import TASK,sha

def verify_requested_job(action,key,window,arm=None,seed=None):
    if action=='PRIOR_CACHE':
        windows=json.loads((TASK/'configs/GPU_RGB_INPUTS.json').read_text())['windows']
        if window not in {w['window_id'] for w in windows} or key!='cache_'+window:raise PermissionError('Cache window/job key mismatch')
        return
    rows=list(csv.DictReader((TASK/'configs/EXECUTION_ORDER.csv').open()))
    matches=[r for r in rows if r['job_key']==key]
    if len(matches)!=1 or (matches[0]['window'],matches[0]['arm'],int(matches[0]['seed']))!=(window,arm,seed):
        raise PermissionError('Requested window/arm/seed differs from authorized frozen job')

def require_approved_runtime(path,action,job_key):
    if not path:raise PermissionError('Formal GPU execution not authorized in this preparation stage')
    p=Path(path)
    if not p.is_file():raise PermissionError('Explicit user authorization file required')
    x=json.loads(p.read_text())
    required=(x.get('stage')=='TASK011D_FORMAL_GPU',x.get('approved') is True,
        x.get('secondary_thresholds_approved') is True,
        bool(x.get('approved_secondary_thresholds')),
        x.get('secondary_proposals_sha256')==sha(TASK/'reports/SECONDARY_THRESHOLD_PROPOSALS.csv'),
        bool(x.get('user_authorization_reference')),not x.get('test_only',False),
        x.get('protocol_sha256')==sha(TASK/'configs/FROZEN_EXPERIMENT_PROTOCOL.json'),
        action in x.get('allowed_actions',[]),job_key in x.get('approved_job_keys',[]))
    if not all(required):raise PermissionError('Authorization scope/hash/secondary-threshold approval does not match')
    protocol=json.loads((TASK/'configs/FROZEN_EXPERIMENT_PROTOCOL.json').read_text())
    for r in protocol['files']:
        if sha(TASK/r['path'])!=r['sha256']:raise PermissionError('Frozen configuration changed')
    implementation=json.loads((TASK/'configs/IMPLEMENTATION_LOCK.json').read_text())
    for r in implementation['files']:
        if sha(TASK/r['path'])!=r['sha256']:raise PermissionError('Reviewed implementation changed')
    return x
