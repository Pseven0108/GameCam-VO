"""Predeclared repeated-development comparisons; no held-out GT inspected."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
jobs=[]
orders={43:['baseline','legacy','neutral','gmos','geomotion','geometry','fusion','static','fusion_static','legacy_mean','depth','depth_static','depth_fusion'],
        44:['depth_fusion','depth_static','depth','legacy_mean','fusion_static','static','fusion','geometry','geomotion','gmos','neutral','legacy','baseline'],
        45:['baseline','geometry','static','legacy','fusion','neutral','legacy_mean','gmos','geomotion','fusion_static','depth','depth_static','depth_fusion']}
for seed,methods in orders.items():
    for method in methods:
        name=f'night007_dev_{method}_s{seed}_r2' if seed==43 and method=='baseline' else f'night007_dev_{method}_s{seed}_r1'
        cmd=['wsl','--exec','sh','/mnt/d/aaa/GameCam-VO-TASK010-A/experiments/TASK010-A/scripts/run_native.sh',
             'experiments/TASK010-A/scripts/run_window.py','--dataset','night007_dev','--method',method,
             '--seed',str(seed),'--priors','/mnt/d/aaa/GameCam-VO-TASK009/experiments/TASK009/outputs/native_priors_216x384_r3',
             '--output','experiments/TASK010-A/outputs/droid/'+name]
        if method.startswith('depth'):
            cmd[cmd.index('--priors')+1]='/mnt/d/aaa/GameCam-VO-TASK010-A/experiments/TASK010-A/outputs/priors_blend/night007_dev'
        if method in ('static','fusion_static','depth_static'):
            cmd+=['--static-tracks','/mnt/d/aaa/GameCam-VO-TASK009/experiments/TASK009/outputs/mdtracker_metric_32f_160x280_fp32_r1']
        jobs.append({'id':name,'command':cmd})
(TASK/'private/development_plan.json').write_text(json.dumps(jobs,indent=2))
print('Prepared',len(jobs),'matched serial native runs; earlier baseline retained as preliminary observer-compatibility run')
