"""Validate only existing outputs; never fill absent keyframes or poses."""
import numpy as np
from control_common import ControlError,file_sha

def validate_run(receipt,pose_path,expected_ids,*,expected_policy_sha,expected_c0_sha):
    required={'exit_code','formal_run_started','input_rgb_ids','policy_sha256','c0_state_sha256','pose_file_sha256','schedule_complete','native_calls_verified','status'}
    if required-set(receipt):raise ControlError('Incomplete run receipt')
    if receipt['exit_code']!=0 or not receipt['formal_run_started'] or receipt['status']!='COMPLETE' or not receipt['schedule_complete'] or not receipt['native_calls_verified']:raise ControlError('Incomplete/failed native run')
    if receipt['input_rgb_ids']!=expected_ids or receipt['policy_sha256']!=expected_policy_sha or receipt['c0_state_sha256']!=expected_c0_sha:raise ControlError('Run identity mismatch')
    if file_sha(pose_path)!=receipt['pose_file_sha256']:raise ControlError('Pose SHA mismatch')
    a=np.load(pose_path,allow_pickle=False)
    if a.shape!=(len(expected_ids),7) or not np.isfinite(a).all():raise ControlError('Missing/invalid full-frame poses')
    if not np.allclose(np.linalg.norm(a[:,3:],axis=1),1,atol=1e-3):raise ControlError('Invalid pose quaternion')
    return {'valid':True,'pose_count':len(a),'direct_keyframe_pose_claim':False}
