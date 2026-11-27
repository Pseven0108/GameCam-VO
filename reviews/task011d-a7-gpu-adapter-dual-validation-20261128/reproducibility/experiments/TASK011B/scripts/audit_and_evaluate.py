"""Actual cached-field audit and paired diagnostics, no torch or new inference."""
import argparse
import importlib.metadata
import json
import os
import platform
import sys
import time
from pathlib import Path

import numpy as np

from common import TASK,PREV_TASK,PROTOCOL,sha,dump,csvwrite,records,load_metrics,load_historical_absrel
from reliability import validity,disagreements,build_scores,fast_risk_coverage,DISAGREEMENTS,METHODS

FIELDS = ['native_depth','flip_depth','native_confidence','flip_confidence',
          'flip_relative_disagreement','flip_log_disagreement','tta_valid',
          'native_bin_entropy','native_bin_variance','native_bin_max_probability','native_effective_bins',
          'native_depth_unclipped','flip_depth_unclipped']


def stats(x):
    x=np.asarray(x);finite=x[np.isfinite(x)]
    result={'elements':int(x.size),'finite':int(np.isfinite(x).sum()),'nan':int(np.isnan(x).sum()),
            'positive_inf':int(np.isposinf(x).sum()),'negative_inf':int(np.isneginf(x).sum()),
            'negative':int((finite<0).sum()),'zero':int((finite==0).sum()),
            'positive_near_zero':int(((finite>0)&(finite<=PROTOCOL['depth_min_native_units'])).sum()),
            'dtype':str(x.dtype),'shape':str(list(x.shape))}
    for q in (0,.01,.5,.9,.95,.99,1):
        result['q'+str(q)]=float(np.quantile(finite.astype(np.float64),q)) if finite.size else None
    return result


def summarize(rows, groupkeys, measures):
    groups={}
    for row in rows:
        key=tuple(row[k] for k in groupkeys)
        groups.setdefault(key,[]).append(row)
    out=[]
    for key,own in groups.items():
        line=dict(zip(groupkeys,key));line['frames']=len(own)
        line['independent_blind_test']=False
        for k in measures:
            v=[r[k] for r in own if r.get(k) is not None]
            line[k+'_mean']=float(np.mean(v)) if v else None
            line[k+'_min']=float(np.min(v)) if v else None
            line[k+'_max']=float(np.max(v)) if v else None
        out.append(line)
    return out


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',default='cpu_001');a=p.parse_args()
    out=TASK/'runs'/a.run
    out.mkdir(parents=True,exist_ok=False)
    if 'torch' in sys.modules:raise RuntimeError('CPU cache experiment must not import torch')
    start=time.perf_counter();metric=load_metrics()
    numeric=[];audit=[];tta_stats=[];results=[];curves=[];bins=[];protection=[];legacy=[];method_counts=[]
    package_list=['numpy','scipy','scikit-learn']
    dump(out/'RUN_CONFIGURATION.json',dict(protocol=PROTOCOL,python=sys.version,
        packages={n:importlib.metadata.version(n) for n in package_list},host=platform.node(),
        core_source_sha256={n:sha(Path(__file__).with_name(n)) for n in ['audit_and_evaluate.py','reliability.py','common.py']},
        no_new_inference=True,primary_depth_predictions_unchanged=True,
        sources='TASK011A cpu_002 frozen arrays plus complete original R2.1 NPZ fields'))
    (out/'derived_maps').mkdir()
    for record in records():
        sample=record['sample'];sid=sample['sample_id'];source=Path(record['local_npz'])
        h=sha(source);before=source.stat()
        if h!=record['sha256']:raise RuntimeError('Original cache hash mismatch: '+sid)
        meta=dict(sample=sid,dataset=sample['dataset'],environment=sample['environment'],sequence=sample['sequence_id'])
        print('AUDIT',sid,flush=True)
        with np.load(source,allow_pickle=False) as z:
            missing=set(FIELDS)-set(z.files)
            if missing:raise RuntimeError('Missing original fields: '+str(missing))
            for name in FIELDS:
                numeric.append(dict(**meta,field=name,**stats(z[name])))
            native=z['native_depth'].astype(np.float64)
            flipped=z['flip_depth'][:,::-1].astype(np.float64)
            conf=z['native_confidence'].astype(np.float64)
            original=z['tta_valid'].copy()
            # Original stored mask and disagreement fields are already native-aligned.
            expected=np.isfinite(native)&np.isfinite(flipped)&(native>0)&(flipped>0)
            if not np.array_equal(original,expected):raise RuntimeError('Stored tta_valid differs from original generation contract')
            saved_relative=z['flip_relative_disagreement'].copy()
        masks=validity(native,flipped,original,PROTOCOL['depth_min_native_units'])
        d=disagreements(native,flipped,masks['pair_valid'],PROTOCOL['disagreement_epsilon_native_units'])
        # This reference intentionally includes zero predictions; never feeds the new controller.
        ungated=np.abs(native-flipped)/(np.abs(native)+PROTOCOL['disagreement_epsilon_native_units'])
        audit.append(dict(**meta,pixels=int(native.size),native_valid=int(masks['native_valid'].sum()),
            flip_valid=int(masks['flip_valid'].sum()),pair_valid=int(masks['pair_valid'].sum()),
            original_tta_invalid=int((~original).sum()),original_mask_exact=True,
            native_valid_pair_invalid=int((masks['native_valid']&~masks['pair_valid']).sum()),
            native_invalid=int((~masks['native_valid']).sum()),zero_native=int((native==0).sum()),zero_flip=int((flipped==0).sum()),
            native_negative=int((native<0).sum()),flip_negative=int((flipped<0).sum()),
            ungated_relative_max=float(np.max(ungated)),ungated_relative_gt_1e6=int((ungated>1e6).sum()),
            saved_relative_nonfinite=int((~np.isfinite(saved_relative)).sum()),depth_unit='FX_SCALED_NETWORK_UNITS_NOT_INDEPENDENT_PHYSICAL_METRES'))
        tta_stats.append(dict(**meta,disagreement='HistoricalUngatedRelative',domain='ALL_FINITE_RAW_INCLUDING_ZEROS',**stats(ungated)))
        for name,values in d.items():
            tta_stats.append(dict(**meta,disagreement=name,domain='PAIR_VALID_ONLY',
                greater_than_10=int((values>10).sum()),greater_than_1000=int((values>1000).sum()),
                greater_than_1e6=int((values>1e6).sum()),**stats(values)))
        # Every score and rank is computed before opening inherited GT errors.
        all_scores={name:build_scores(conf,values,masks,PROTOCOL['primary_fusion_native_weight']) for name,values in d.items()}
        primary=all_scores[PROTOCOL['primary_disagreement']]
        saved={**masks,'native_depth':native.astype(np.float32),'flip_aligned_depth':flipped.astype(np.float32),
               'native_confidence':conf.astype(np.float32),**{'tta_'+k:v for k,v in d.items()}}
        for method,field in primary.items():
            saved.update({method+'_'+k:v for k,v in field.items()})
            method_counts.append(dict(**meta,method=method,prior_allowed=int(field['prior_allowed'].sum()),
                prior_allowed_fraction=float(field['prior_allowed'].mean()),native_fallback=int(field['native_fallback'].sum()),
                undefined_risk=int((~np.isfinite(field['risk'])).sum()),invalid_native_prior_weight_nonzero=int((field['reliability'][~masks['native_valid']]!=0).sum())))
        historic=load_historical_absrel(sid)
        if 'valid_GT' in historic:
            valid_gt=historic['valid_GT'];error=historic['AbsRel']
            if not(error.shape==native.shape==valid_gt.shape):raise RuntimeError('Inherited GT error grid differs')
            if not np.isfinite(error[valid_gt]).all():raise RuntimeError('Inherited error invalid')
            saved.update(valid_GT=valid_gt,AbsRel=error)
            for disagreement,methods in all_scores.items():
                for method,field in methods.items():
                    for domain in ('FULL_GT_ZERO_EXTENDED_REJECTION_POLICY','COMMON_VALID_PAIR_DIAGNOSTIC_NOT_GATE_PASS'):
                        mask=valid_gt.copy()
                        if domain.startswith('COMMON'):mask &= masks['pair_valid']&np.isfinite(conf)
                        if not mask.any():raise RuntimeError('No GT in declared evaluation domain')
                        e=error[mask];s=field['policy_diagnostic_risk'][mask]
                        rc=fast_risk_coverage(e,s);corr=metric.correlation(e,s)
                        line=dict(**meta,disagreement=disagreement,method=method,domain=domain,n=int(mask.sum()),
                            zero_native_in_evaluation=int(((native==0)&mask).sum()),prior_eligible_on_GT=int((mask&field['prior_allowed']).sum()),
                            AUSE=rc['AUSE_raw_AbsRel'],AURG=rc['AURG_raw_AbsRel'],Spearman=corr['Spearman'],Pearson=corr['Pearson'],
                            mean_AbsRel=float(e.mean()),AbsRel_P50=float(np.quantile(e,.5)),AbsRel_P90=float(np.quantile(e,.9)))
                        for threshold in PROTOCOL['event_thresholds']:
                            rank=metric.binary_ranking(e>threshold,s)
                            line['AUROC_gt_'+str(threshold)]=rank['AUROC'];line['AP_gt_'+str(threshold)]=rank['AUPRC']
                        for coverage in PROTOCOL['retained_coverages']:
                            line['AbsRel_at_coverage_'+str(coverage)]=float(np.interp(coverage,rc['coverage'],rc['risk']))
                        results.append(line)
                        if disagreement==PROTOCOL['primary_disagreement']:
                            for coverage in np.linspace(0,1,101):
                                curves.append(dict(**meta,method=method,domain=domain,coverage=float(coverage),
                                    risk=float(np.interp(coverage,rc['coverage'],rc['risk'])),oracle=float(np.interp(coverage,rc['coverage'],rc['oracle'])),
                                    random=float(e.mean())))
                            for row in metric.reliability_bins(e,s):bins.append(dict(**meta,method=method,domain=domain,**row))
            legacy_methods={'LegacyNative':historic['rank_native'],'LegacyFlip':historic['rank_flip'],
                            'LegacyRankFusion':historic['risk_fusion'],'LegacyMaxFusion':historic['risk_max']}
            for method,risk in legacy_methods.items():
                rc=fast_risk_coverage(error[valid_gt],risk[valid_gt]);rank=metric.binary_ranking(error[valid_gt]>.2,risk[valid_gt])
                legacy.append(dict(**meta,method=method,n=int(valid_gt.sum()),zero_native=int(((native==0)&valid_gt).sum()),
                    AUROC=rank['AUROC'],AP=rank['AUPRC'],AUSE=rc['AUSE_raw_AbsRel'],AURG=rc['AURG_raw_AbsRel'],
                    **metric.correlation(error[valid_gt],risk[valid_gt])))
        np.savez_compressed(out/'derived_maps'/(sid+'.npz'),**saved)
        if sha(source)!=h or source.stat().st_mtime_ns!=before.st_mtime_ns:raise RuntimeError('Original cache changed')
        protection.append(dict(path=str(source),sha256=h,bytes=before.st_size,mtime_ns=before.st_mtime_ns,unchanged=True))
    csvwrite(out/'TTA_VALIDITY_AUDIT.csv',audit)
    csvwrite(out/'TTA_NUMERICAL_STATISTICS.csv',numeric)
    csvwrite(out/'TTA_DISAGREEMENT_COMPARISON.csv',tta_stats)
    csvwrite(out/'RELIABILITY_METHOD_COMPARISON.csv',results)
    csvwrite(out/'VALIDITY_AWARE_FUSION.csv',method_counts)
    csvwrite(out/'RISK_COVERAGE_COMPARISON.csv',curves)
    csvwrite(out/'ERROR_BINS.csv',bins)
    csvwrite(out/'HISTORICAL_ALL_PIXELS_COMPARISON.csv',legacy)
    eval_rows=[r for r in results if r['sequence']=='0001']
    measures=['AUROC_gt_0.1','AUROC_gt_0.2','AUROC_gt_0.5','AP_gt_0.2','AUSE','AURG','Spearman','Pearson',
              *['AbsRel_at_coverage_'+str(x) for x in PROTOCOL['retained_coverages']]]
    csvwrite(out/'MVS_OBSERVED_SEQUENCE_MACRO.csv',summarize(eval_rows,['disagreement','method','domain'],measures))
    csvwrite(out/'ENVIRONMENT_COMPARISON.csv',summarize(method_counts,['environment','method'],['prior_allowed_fraction','native_fallback']))
    dump(out/'ORIGINAL_CACHE_PROTECTION.json',dict(status='PASS',files=protection,originals_overwritten=False))
    dump(out/'COMPLETION.json',dict(status='COMPLETE_CPU_R0_R1',seconds=time.perf_counter()-start,
        cached_samples=len(audit),metric_rows=len(results),new_model_forwards=0,
        strict_depth_GT_gate='STILL_FAILED_NOT_REINTERPRETED',
        diagnostic='Seven zero predictions retained in full-GT policy ranking, no pixels discarded',
        VIPER_GT_accuracy_measured=False,original_caches_preserved=True))
    dump(TASK/'private/LATEST_CPU_RUN.json',dict(path=str(out),status='COMPLETE_CPU_R0_R1'))
    print('CPU_R0_R1_COMPLETE',time.perf_counter()-start,flush=True)


if __name__=='__main__':
    main()
