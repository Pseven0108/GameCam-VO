"""Summarize sample lower bounds, keeping missing measurements explicit."""
import json
from collections import defaultdict
from common import TASK,csvwrite,dump


def main():
    path=TASK/'private/runtime_resource_samples_001.jsonl'
    samples=[json.loads(s) for s in path.read_text().splitlines()]
    by=defaultdict(list)
    for r in samples:
        if r.get('sample_failed'):continue
        raw=r['gpu']['stdout'].strip().split(',')
        gpu_used=float(raw[1]) if len(raw)==3 else None
        for job in r['running']:
            by[job['label']].append(dict(shm_used_bytes=24*1024**3-r['shm_free_bytes'],
                data_free_bytes=r['data_free_bytes'],gpu_used_mib=gpu_used))
    rows=[]
    for key,values in sorted(by.items()):
        rows.append(dict(job=key,samples=len(values),sample_seconds=20,
            sampled_shm_peak_used_bytes=max(r['shm_used_bytes'] for r in values),
            sampled_gpu_total_peak_MiB=max(r['gpu_used_mib'] for r in values if r['gpu_used_mib'] is not None),
            sampled_minimum_data_free_bytes=min(r['data_free_bytes'] for r in values),
            true_peak_may_be_higher=True,device_total_includes_preexisting_allocation=True))
    csvwrite(TASK/'evaluation/VIPER_SAMPLED_RESOURCES.csv',rows)
    missing=[]
    for p in (TASK/'gpu_results/receipts').glob('window_*.json'):
        if p.stem not in by:missing.append(p.stem)
    dump(TASK/'evaluation/RESOURCE_SAMPLE_COVERAGE.json',dict(
        samples=len(samples),failed_sample_reads=sum(r.get('sample_failed',False) for r in samples),
        measured_jobs=len(rows),unmeasured_window_jobs=missing,interval_seconds=20,
        peak_values_are_sample_lower_bounds=True,shm_mount_capacity_bytes=24*1024**3,
        cannot_infer_exclusive_model_gpu_peak_by_subtracting_stale_pid=True))
    print('RESOURCE_SAMPLES_SUMMARIZED',len(samples),len(rows),flush=True)


if __name__=='__main__':main()
