"""Recheck all 240 real diagnostic rows from shared arrays, no GT file/model."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from common import TASK,dump,load_metrics
from reliability import validity,disagreements,build_scores,fast_risk_coverage


def verify(run):
    run=Path(run)
    expected=list(csv.DictReader((run/'RELIABILITY_METHOD_COMPARISON.csv').open(encoding='utf-8-sig')))
    by_sample={}
    for row in expected:by_sample.setdefault(row['sample'],[]).append(row)
    metric=load_metrics();maps_checked=0;scalars=0;worst=0.;samples=0;zero_counts={}
    for path in sorted((run/'derived_maps').glob('*.npz')):
        sid=path.stem
        with np.load(path,allow_pickle=False) as z:a={k:z[k].copy() for k in z.files}
        masks=validity(a['native_depth'],a['flip_aligned_depth'],a['original_tta_valid'])
        for key,mask in masks.items():np.testing.assert_array_equal(mask,a[key]);maps_checked+=1
        tta=disagreements(a['native_depth'],a['flip_aligned_depth'],masks['pair_valid'])
        for key,field in tta.items():np.testing.assert_array_equal(field,a['tta_'+key]);maps_checked+=1
        scores={key:build_scores(a['native_confidence'],field,masks) for key,field in tta.items()}
        for method,fields in scores['SymmetricRelative'].items():
            for key,field in fields.items():
                np.testing.assert_array_equal(field,a[method+'_'+key]);maps_checked+=1
        for row in by_sample.get(sid,[]):
            mask=a['valid_GT'].copy()
            if row['domain'].startswith('COMMON'):mask&=masks['pair_valid']&np.isfinite(a['native_confidence'])
            if int(mask.sum())!=int(row['n']):raise AssertionError('Evaluation population changed')
            err=a['AbsRel'][mask];risk=scores[row['disagreement']][row['method']]['policy_diagnostic_risk'][mask]
            rc=fast_risk_coverage(err,risk);corr=metric.correlation(err,risk)
            values=dict(AUSE=rc['AUSE_raw_AbsRel'],AURG=rc['AURG_raw_AbsRel'],Spearman=corr['Spearman'],Pearson=corr['Pearson'])
            for threshold in (.1,.2,.5):
                rank=metric.binary_ranking(err>threshold,risk)
                values['AUROC_gt_'+str(threshold)]=rank['AUROC'];values['AP_gt_'+str(threshold)]=rank['AUPRC']
            for coverage in (.2,.4,.6,.8):
                values['AbsRel_at_coverage_'+str(coverage)]=float(np.interp(coverage,rc['coverage'],rc['risk']))
            for key,value in values.items():
                if value is None:
                    if row[key]!='':raise AssertionError('Undefined metric changed')
                else:
                    delta=abs(value-float(row[key]));worst=max(worst,delta)
                    if delta>1e-12:raise AssertionError('Artifact replay differs: '+sid+' '+key)
                    scalars+=1
            if row['domain'].startswith('FULL'):
                zero_counts[sid]=int(((a['native_depth']==0)&mask).sum())
        samples+=1
    if zero_counts.get('MVS_0001_0099')!=7:raise AssertionError('Historical seven zeros were lost')
    return dict(status='PASS',samples=samples,array_comparisons=maps_checked,metric_rows=len(expected),
        scalar_comparisons=scalars,maximum_absolute_difference=worst,atol=1e-12,
        original_seven_zero_predictions_retained=True,model_or_GPU_used=False,raw_GT_required=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,default=TASK/'runs/cpu_003')
    parser.add_argument('--output',type=Path,default=TASK/'runs/cpu_003/ARTIFACT_REPLAY_VERIFICATION.json')
    args=parser.parse_args();result=verify(args.run);dump(args.output,result);print(json.dumps(result,indent=2))
