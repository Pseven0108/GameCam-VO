"""Freeze code/config identities after all preparation fixes, before review."""
import json
from common import TASK,dump,sha

def main():
    critical=['uniform_control.py','authorization.py','collect_snapshots.py','fixed_state_replay.py',
        'run_end_to_end.py','native_binding.py','runtime.py','native_driver.py','cache_priors.py',
        'analyze_results.py','score_completed_runs.py','transfer_audit.py']
    paths=[TASK/n for n in critical]+sorted((TASK/'tests').glob('*.py'))+sorted((TASK/'frozen_metrics').glob('*.py'))
    dump(TASK/'configs/IMPLEMENTATION_LOCK.json',dict(files=[dict(path=p.relative_to(TASK).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in paths],
        algorithm_tuned_on_TASK011D_results=False,model_runs=0))
    p=TASK/'configs/FROZEN_EXPERIMENT_PROTOCOL.json';x=json.loads(p.read_text())
    x['files']=[dict(path=q.relative_to(TASK).as_posix(),bytes=q.stat().st_size,sha256=sha(q)) for q in sorted((TASK/'configs').rglob('*')) if q.is_file() and q!=p]
    x['secondary_threshold_proposals_sha256']=sha(TASK/'reports/SECONDARY_THRESHOLD_PROPOSALS.csv')
    x['formal_SLAM_GPU_not_started']=True;x['synthetic_CUDA_executed']=True
    dump(p,x)
    print('CODE_AND_CONFIG_FROZEN_FOR_REVIEW',len(paths),len(x['files']))

if __name__=='__main__':main()
