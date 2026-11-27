"""Observed cache, service, model and archive costs; no cold-runtime inference."""
import csv,json
import numpy as np
from pathlib import Path
from common import TASK,csvwrite,dump


def service(label):
    p=TASK/'gpu_results/service_logs'/(label+'.stdout')
    return json.loads(p.read_text().strip().splitlines()[-1])


def main():
    receipts=TASK/'gpu_results/receipts'
    windows=json.loads((TASK/'private/VIPER_INPUTS.json').read_text())['windows']
    cache_rows=[];run_rows=[]
    for w in windows:
        label='cache_'+w['window_id'];r=json.loads((receipts/(label+'.json')).read_text())
        meta=json.loads((Path(r['local_extracted'])/'CACHE_RECEIPT.json').read_text())
        if meta['precision_protocol']!='NATIVE_MOTION_FILTER_AUTOCAST_V2':raise RuntimeError('Wrong precision cache')
        cache_rows.append(dict(window=w['window_id'],environment=w['environment'],
            frames=meta['frames'],model_forwards=meta['model_forwards'],
            cache_prediction_seconds=meta['seconds'],cache_service_seconds=service(label)['seconds'],
            archive_bytes=r['bytes'],source_full_resolution_arrays_retained=True,
            actual_metric_focal=meta['actual_metric_focal'],
            tracker_fx=meta['actual_tracker_K'][0],tracker_fy=meta['actual_tracker_K'][1]))
        for i in range(7):
            aid='A'+str(i);label='window_'+w['window_id']+'_'+aid
            r=json.loads((receipts/(label+'.json')).read_text());root=Path(r['local_extracted'])
            complete=root/'COMPLETE.json';child=root/'TRACKING_CHILD_COMPLETE.json'
            m=json.loads(complete.read_text()) if complete.exists() else {}
            c=json.loads(child.read_text()) if child.exists() else {}
            run_rows.append(dict(window=w['window_id'],environment=w['environment'],arm=aid,
                status='COMPLETE' if complete.exists() else 'ALGORITHM_FAILURE',
                service_seconds=service(label)['seconds'],model_run_seconds=m.get('seconds'),
                tracking_child_seconds=c.get('seconds'),archive_bytes=r['bytes'],
                peak_allocated_bytes=c.get('peak_allocated_bytes'),peak_reserved_bytes=c.get('peak_reserved_bytes'),
                shared_cache_prediction_seconds=meta['seconds'],
                A0_live_first_frame_check_included=aid=='A0',
                extra_native_regression_included=aid=='A0' and w is windows[0],
                GPU_compute_and_transfer_not_timed_as_one_cold_deployment=True))
    csvwrite(TASK/'evaluation/VIPER_SHARED_PRIOR_CACHE_COSTS.csv',cache_rows)
    csvwrite(TASK/'evaluation/VIPER_RUNTIME_ARCHIVE_COSTS.csv',run_rows)
    summaries=[];paired=[]
    fields=('service_seconds','model_run_seconds','tracking_child_seconds','peak_allocated_bytes')
    for arm in ('A0','A1','A2','A3','A4','A5','A6'):
        for scope in ('ALL_PLANNED_OUTCOMES','COMPLETE_TRAJECTORIES_ONLY'):
            own=[r for r in run_rows if r['arm']==arm and (scope=='ALL_PLANNED_OUTCOMES' or r['status']=='COMPLETE')]
            row=dict(arm=arm,population=scope,outcomes=len(own),shared_prior_cache_excluded=True)
            for key in fields:
                values=[float(r[key]) for r in own if r.get(key) is not None]
                row[key+'_n']=len(values);row[key+'_mean']=float(np.mean(values)) if values else None
                row[key+'_median']=float(np.median(values)) if values else None
            summaries.append(row)
    by={(r['window'],r['arm']):r for r in run_rows}
    for reference in ('A0','A1','A4'):
        for arm in ('A2','A3','A4','A5','A6'):
            if arm==reference:continue
            differences=[]
            for w in windows:
                x,y=by[(w['window_id'],arm)],by[(w['window_id'],reference)]
                if x['status']=='COMPLETE' and y['status']=='COMPLETE':
                    differences.append(x['service_seconds']-y['service_seconds'])
            if not differences:continue
            d=np.asarray(differences);rng=np.random.default_rng(43)
            ci=np.quantile(d[rng.integers(0,len(d),size=(3000,len(d)))].mean(1),[.025,.975]) if len(d)>1 else [None,None]
            paired.append(dict(arm=arm,reference=reference,paired_complete_sequences=len(d),
                service_seconds_mean_difference=float(d.mean()),service_seconds_median_difference=float(np.median(d)),
                lower95=ci[0],upper95=ci[1],shared_cache_excluded=True,
                A0_extra_validation_included=reference=='A0',exploratory_not_clean_cold_deployment=True))
    csvwrite(TASK/'evaluation/VIPER_RUNTIME_METHOD_SUMMARY.csv',summaries)
    csvwrite(TASK/'evaluation/VIPER_RUNTIME_PAIRED_SERVICE_COSTS.csv',paired)
    dump(TASK/'evaluation/RESOURCE_COST_DEFINITION.json',dict(
        window_count=len(cache_rows),run_count=len(run_rows),
        total_shared_cache_prediction_seconds=sum(r['cache_prediction_seconds'] for r in cache_rows),
        total_cache_service_seconds=sum(r['cache_service_seconds'] for r in cache_rows),
        total_window_service_seconds=sum(r['service_seconds'] for r in run_rows),
        original_archive_bytes=sum(r['archive_bytes'] for r in cache_rows+run_rows),
        runtime_comparison_is_cache_assisted=True,cold_end_to_end_deployment_measured=False,
        model_construction_retained=True,A0_extra_live_cache_checks=True,
        first_A0_extra_8_native_regression_BA_and_1_geometry_probe=True,
        service_seconds_scope='Entire window Python process including imports/model construction/spawn/reliability maps/tracking/finalBA/filler; excludes common prior-cache generation and result archival/transfer.',
        model_run_seconds_scope='After SLAM constructor, before model.run; includes spawn and child reliability-map preparation, tracking/finalBA/filler; excludes parent SLAM construction and shared cache.',
        tracking_child_seconds_scope='Timer starts only after cached coefficient maps/candidate import/controller setup; includes native tracking/finalBA/filler, not all controller-preparation cost.',
        transfer_and_archive_overhead_not_measured_as_GPU_inference=True,
        device_memory_samples_include_preexisting_driver_reported_allocation=True))
    print('ACTUAL_RUNTIME_AND_STORAGE_COSTS',len(cache_rows),len(run_rows),flush=True)


if __name__=='__main__':main()
