"""Evidence tables from actual receipts, resource logs and arrays; no new GPU work."""
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
os.environ['MPLCONFIGDIR']='D:/aaa/caches/task010a/matplotlib'


def write_csv(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for row in rows for k in row))
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def c2w(p):
    mat=np.tile(np.eye(4),(len(p),1,1));mat[:,:3,:3]=Rotation.from_quat(p[:,3:]).as_matrix();mat[:,:3,3]=p[:,:3]
    return np.linalg.inv(mat)


def main():
    ds={d['name']:d for d in json.loads((TASK/'private/DATA_MANIFEST.json').read_text())}
    models=[];aux=[];resources=[];stages=[];segments=[];receipts=[]
    wall={}
    for state in (TASK/'private').glob('*STATE.json'):
        value=json.loads(state.read_text())
        for job in value.get('jobs',[]):
            if job.get('status')=='COMPLETE' and 'seconds' in job:wall[job['id']]=job['seconds']
    spec=importlib.util.spec_from_file_location('sealed_metrics',ROOT/'experiments/TASK009/scripts/evaluate_trajectories.py')
    metric=importlib.util.module_from_spec(spec);spec.loader.exec_module(metric)
    for model in ['gmos','pi3mos','geomotion','geomotion_full']:
        for name,d in ds.items():
            folder=TASK/'outputs'/model/name;rp=folder/'receipt.json'
            if not rp.exists():continue
            r=json.loads(rp.read_text())
            if r['status']!='COMPLETE':continue
            frame_rows=r.get('frames',[]);encoder=r.get('encoder_timings',[])
            peaks=[f.get('peak_allocated_bytes',0) for f in frame_rows+encoder]
            prediction_seconds=[f.get('seconds',f.get('chunk_seconds',0)) for f in frame_rows]
            models.append({'dataset':name,'model':model,'frames':len(frame_rows),'load_forward_save_seconds_excluding_Python_import':r.get('total_seconds'),
                'amortized_model_pipeline_seconds_per_target':r['total_seconds']/len(frame_rows) if frame_rows and 'total_seconds' in r else None,
                'peak_tensor_allocated_MiB':max(peaks)/1024**2 if peaks and max(peaks)>0 else None,
                'Full_module_CPU_offload':r.get('FP32_module_storage_offload',False),
                'parameter_precision':'FP32; BF16 operations where recorded',
                'timing_includes_startup_IO':True,'reused_historical_receipt':r.get('reused_sealed_TASK008',False),'SAM2_postrefinement':False,
                'context_protocol':str(r.get('temporal_context',r.get('context_offsets','see original receipt'))),
                'depth_semantics':'Relative local z, not admitted physical metres',
                'confidence_semantics':'Raw motion logits, not depth confidence' if model.startswith('geomotion') else 'Uncalibrated model score'})
            for fid in d['rgb_ids']:
                path=folder/f'{fid:05d}.npz'
                with np.load(path,allow_pickle=False) as z:
                    for key in ['probability','confidence','depth']:
                        if key not in z.files:continue
                        a=z[key]
                        aux.append({'dataset':name,'model':model,'rgb_id':fid,'field':key,'finite_fraction':float(np.isfinite(a).mean()),
                            'min':float(a.min()),'p05':float(np.quantile(a,.05)),'median':float(np.median(a)),
                            'p95':float(np.quantile(a,.95)),'max':float(a.max()),
                            'calibrated_probability':False,'physical_metric_GT_available':False})
    for run in sorted((TASK/'outputs/droid').glob('*')):
        rp=run/'receipt.json'
        if not rp.exists():continue
        r=json.loads(rp.read_text());receipts.append({'run':run.name,**r})
        if r['status']!='COMPLETE':continue
        resource=TASK/'private'/('resources_'+run.name+'.jsonl');samples=[];host=[]
        if resource.exists():
            for line in resource.read_text().splitlines():
                q=json.loads(line);key=next((k for k in q if k.startswith('gpu_memory') or k=='whole_GPU_memory_utilization'),None)
                if key:
                    try:samples.append([float(x.strip()) for x in q[key].split(',')])
                    except ValueError:pass
                if 'host_cpu_percent' in q:host.append(q['host_cpu_percent'])
        resources.append({'run':run.name,'dataset':r['dataset'],'method':r['method'],'seed':r['seed'],
            'tracking_finalBA_filler_seconds':r['total_seconds'],'tracking_seconds':r['tracking_seconds'],
            'native_FPS_excluding_prior_import_model_init':r['frames']/r['total_seconds'],
            'fresh_child_wall_seconds':wall.get(run.name),
            'import_model_init_IO_and_monitor_overhead_seconds':wall[run.name]-r['total_seconds'] if run.name in wall else None,
            'peak_tensor_allocated_MiB':r['peak_allocated_bytes']/1024**2,
            'peak_tensor_reserved_MiB':r['peak_reserved_bytes']/1024**2,
            'whole_card_peak_used_MiB':max((x[0] for x in samples),default=None),
            'whole_card_mean_utilization_percent':float(np.mean([x[1] for x in samples])) if samples else None,
            'whole_host_mean_CPU_percent':float(np.mean(host)) if host else None,
            'auxiliary_models_cached_not_in_FPS':True,'resource_scope_includes_desktop':True})
        calls=[json.loads(s) for s in (run/'native_ba_observations/calls.jsonl').read_text().splitlines()]
        for phase in sorted(set(c.get('phase','PRELIMINARY_UNPHASED') for c in calls)):
            subset=[c for c in calls if c.get('phase','PRELIMINARY_UNPHASED')==phase]
            support=[c['geometric_valid_proxy_count'] for c in subset if 'geometric_valid_proxy_count' in c]
            stages.append({'run':run.name,'phase':phase,'calls':len(subset),
                'geometric_valid_proxy_count_mean':float(np.mean(support)) if support else None,
                'positive_weight_fraction_mean':float(np.mean([c['positive_weight_fraction'] for c in subset])),
                'source_U_median_mean':float(np.mean([c['u_median'] for c in subset])),
                'source_U_p95_mean':float(np.mean([c['u_p95'] for c in subset])),
                'native_effective_correspondence_counter':False})
        d=ds[r['dataset']]
        with np.load(d['offline_gt'],allow_pickle=False) as z:truth=z['c2w'];ids=z['rgb_ids']
        with np.load(run/'trajectory.npz',allow_pickle=False) as z:estimate=z['c2w']
        s,rot,t=metric.alignment(estimate[:,:3,3],truth[:,:3,3]);aligned=metric.transform(estimate,s,rot,t)
        # A single whole-window Sim3; every segment retains that same scale.
        for start,end in [(0,15),(16,31),(0,31)]:
            pred=aligned[end,:3,3]-aligned[start,:3,3];gt=truth[end,:3,3]-truth[start,:3,3]
            length=np.linalg.norm(gt)
            segments.append({'run':run.name,'source_rgb':int(ids[start]),'target_rgb':int(ids[end]),
                'global_scaled_displacement_ratio':float(np.linalg.norm(pred)/length) if length>1e-12 else None,
                'global_scaled_vector_error':float(np.linalg.norm(pred-gt)),
                'reference_unit':d['pose_unit'],'per_segment_scale_fit':False})
    out=TASK/'07_cross_scene_evaluation'
    write_csv(TASK/'03_candidate_inference/MODEL_RUNTIME_AND_INTERFACES.csv',models)
    write_csv(TASK/'03_candidate_inference/RAW_AUXILIARY_DISTRIBUTIONS.csv',aux)
    write_csv(out/'NATIVE_RESOURCE_PERFORMANCE.csv',resources)
    write_csv(out/'NATIVE_BA_PHASE_OBSERVATIONS.csv',stages)
    write_csv(out/'GLOBAL_SCALE_SEGMENT_DIAGNOSTICS.csv',segments)
    (TASK/'09_reproducibility/RUN_RECEIPT_INDEX.json').write_text(json.dumps(receipts,indent=2))
    print(json.dumps({'model_windows':len(models),'auxiliary_arrays':len(aux),'native_runs':len(resources),'phase_rows':len(stages)}))


if __name__=='__main__':main()
