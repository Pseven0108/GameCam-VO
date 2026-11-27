"""Post-selection descriptive input audit; GT never changes the fixed windows."""
import json
import numpy as np
from scipy.spatial.transform import Rotation
from common import TASK,csvwrite,dump


def main():
    local=json.loads((TASK/'private/VIPER_INPUTS.json').read_text())['windows']
    rgb={x['window_id']:x for x in json.loads((TASK/'configs/GPU_RGB_INPUTS.json').read_text())['windows']}
    rows=[]
    for w in local:
        r=rgb[w['window_id']]
        ids=[x['rgb_id'] for x in r['frames']]
        if ids!=list(range(w['rgb_start'],w['rgb_end']+1)):raise RuntimeError('Frozen window is not contiguous')
        with np.load(w['offline_gt'],allow_pickle=False) as z:
            gt=z['gt_c2w'].copy()
            if z['rgb_ids'].tolist()!=ids:raise RuntimeError('Offline Camera/RGB identity mismatch')
        p=gt[:,:3,3];step=np.linalg.norm(np.diff(p,axis=0),axis=1)
        rotation=gt[:,:3,:3]
        angles=np.degrees(Rotation.from_matrix(np.swapaxes(rotation[:-1],1,2)@rotation[1:]).magnitude())
        rows.append(dict(window=w['window_id'],sequence=w['sequence'],environment=w['environment'],
            frames=len(ids),unique_RGB_SHA256=len({x['sha256'] for x in r['frames']}),
            exact_repeated_file_count=len(ids)-len({x['sha256'] for x in r['frames']}),
            GT_path_native_units=float(step.sum()),GT_endpoint_native_units=float(np.linalg.norm(p[-1]-p[0])),
            GT_translation_step_median=float(np.median(step)),GT_translation_step_max=float(step.max()),
            GT_rotation_step_median_deg=float(np.median(angles)),GT_rotation_step_max_deg=float(angles.max()),
            GT_rotation_total_angle_sum_deg=float(angles.sum()),
            source_calibration_span_px=w['source_K_span_px'],
            used_for_window_or_parameter_selection=False,metre_accuracy_newly_certified=False))
    csvwrite(TASK/'evaluation/VIPER_INPUT_MOTION_AND_FILE_IDENTITY.csv',rows)
    dump(TASK/'evaluation/INPUT_DESCRIPTION_STATUS.json',dict(
        status='READ_ONLY_POST_SELECTION_DESCRIPTION',windows=len(rows),new_model_forwards=0,
        windows_changed=False,GT_passed_to_tracking=False,
        fast_rotation_dynamic_objects_blur_not_guaranteed_by_midpoint_selection=True,
        distinct_sequences_not_proof_of_population_independence=True))
    print('ACTUAL_FIXED_INPUT_DESCRIPTIONS',len(rows),flush=True)


if __name__=='__main__':main()
