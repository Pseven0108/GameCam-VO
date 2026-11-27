"""Offline scoring, strictly after inference, with paired unit-aware summaries."""
import csv
import importlib.util
import json
import os
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
os.environ['MPLCONFIGDIR']='D:/aaa/caches/task010a/matplotlib'
spec=importlib.util.spec_from_file_location('sealed_task009_metrics',ROOT/'experiments/TASK009/scripts/evaluate_trajectories.py')
metrics=importlib.util.module_from_spec(spec);spec.loader.exec_module(metrics)


def main():
    ds={x['name']:x for x in json.loads((TASK/'private/DATA_MANIFEST.json').read_text())}
    out=TASK/'07_cross_scene_evaluation';out.mkdir(exist_ok=True)
    rows=[]
    for directory in sorted((TASK/'outputs/droid').glob('*')):
        receipt_path=directory/'receipt.json'
        if not receipt_path.exists():
            rows.append({'run':directory.name,'status':'MISSING_TERMINAL_RECEIPT'});continue
        receipt=json.loads(receipt_path.read_text())
        row={'run':directory.name,'dataset':receipt['dataset'],'method':receipt['method'],
             'seed':receipt['seed'],'status':receipt['status']}
        if receipt['status']=='COMPLETE':
            dataset=ds[receipt['dataset']]
            with np.load(dataset['offline_gt'],allow_pickle=False) as z:
                ids=z['rgb_ids'];truth=z['c2w']
            with np.load(directory/'trajectory.npz',allow_pickle=False) as z:
                if not np.array_equal(ids,z['rgb_ids']):raise ValueError('Frame pairing mismatch')
                try:
                    result,aligned,error=metrics.score(z['c2w'],truth,ids)
                except ValueError as exc:
                    # A finite collapsed trajectory must not disappear from the
                    # denominator or be awarded a fabricated zero Sim3 error.
                    if 'No estimated translation' not in str(exc):raise
                    row.update(status='COMPLETE_UNSCORABLE_SIM3',scoring_error=str(exc),
                        reference_unit=dataset['pose_unit'],domain=dataset['domain'],
                        frames=len(ids),coverage=1.,accuracy_failure=True)
                    rows.append(row);continue
            # The reused function's historical field labels do not change real-data units.
            result={k.replace('_game_units','_native_reference_units'):v for k,v in result.items()}
            row.update(result,reference_unit=dataset['pose_unit'],domain=dataset['domain'],
                environment=dataset['environment'],split=dataset['split'],keyframes=receipt['keyframes'],
                runtime_seconds=receipt['total_seconds'],peak_allocated_bytes=receipt['peak_allocated_bytes'],
                normalized_sim3_ate=result['sim3_ate_native_reference_units']/max(result['gt_path_length_native_reference_units'],1e-12))
            np.savez_compressed(out/(directory.name+'_aligned.npz'),rgb_ids=ids,c2w=aligned,per_frame_error=error)
        rows.append(row)
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with (out/'ALL_RUN_METRICS.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    (out/'ALL_RUN_METRICS.json').write_text(json.dumps(rows,indent=2))
    print(json.dumps([{k:r.get(k) for k in ('run','status','sim3_ate_native_reference_units','rpe_translation_offset1_native_reference_units','normalized_sim3_ate','keyframes')} for r in rows],indent=2))


if __name__=='__main__':main()
