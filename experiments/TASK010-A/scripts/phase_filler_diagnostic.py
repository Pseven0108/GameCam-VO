"""Offline stage/end-point accounting; never label filled poses as direct BA poses."""
import csv
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
rows=[];endpoints=[]
for run in sorted((TASK/'outputs/droid').glob('*')):
    if not (run/'receipt.json').exists():continue
    r=json.loads((run/'receipt.json').read_text())
    if r['status']!='COMPLETE':continue
    with np.load(run/'keyframes.npz',allow_pickle=False) as z:ids=z['rgb_ids'];p=z['poses_w2c']
    with np.load(run/'before_final_ba.npz',allow_pickle=False) as z:before=z['poses_w2c'];timestamps=z['timestamps']
    with np.load(run/'trajectory.npz',allow_pickle=False) as z:all_ids=z['rgb_ids'];poses=z['c2w']
    mat=np.tile(np.eye(4),(len(ids),1,1));mat[:,:3,:3]=Rotation.from_quat(p[:,3:]).as_matrix();mat[:,:3,3]=p[:,:3]
    direct=np.linalg.inv(mat);indices=[int(np.flatnonzero(all_ids==fid)[0]) for fid in ids]
    if not np.array_equal(all_ids[timestamps.astype(int)],ids):raise RuntimeError('Final BA keyframe identity changed; do not silently pair by position')
    output_error=float(np.max(abs(direct-poses[indices])))
    rotation=Rotation.from_quat(before[:,3:]).inv()*Rotation.from_quat(p[:,3:])
    rows.append({'run':run.name,'dataset':r['dataset'],'method':r['method'],'seed':r['seed'],
        'direct_keyframes':len(ids),'Filler_frames':len(all_ids)-len(ids),
        'Final_BA_raw_w2c_translation_change_mean':float(np.linalg.norm(p[:,:3]-before[:,:3],axis=1).mean()),
        'Final_BA_rotation_change_mean_deg':float(np.degrees(rotation.magnitude()).mean()),
        'direct_keyframe_vs_export_max_matrix_abs':output_error,
        'forced_keyframe_schedule':True,'natural_keyframe_selection_improvement_tested':False,
        'raw_changes_are_not_metric_pose_accuracy':True})
    if r['dataset']=='night007_dev':
        for a,b in [(309,325),(312,328),(301,332)]:
            endpoints.append({'run':run.name,'source_rgb':a,'target_rgb':b,
                'source_retained_keyframe':a in ids,'target_retained_keyframe':b in ids,
                'both_direct_keyframes':a in ids and b in ids,'source_exported':a in all_ids,'target_exported':b in all_ids,
                'source_Filler':a not in ids,'target_Filler':b not in ids,'filled_pose_is_direct_BA_pose':False})
for name,records in [('STAGE_AND_FILLER_ACCOUNTING.csv',rows),('NIGHT_ENDPOINT_TYPES.csv',endpoints)]:
    with (TASK/'07_cross_scene_evaluation'/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
print('Direct/final-export pose and Filler endpoint accounting',len(rows),'runs')
