"""Single current-task continuation: Full detector -> dev -> frozen paired transfer."""
import json
import argparse
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
PY='D:/aaa/envs/gamecam-vo/python.exe'


def wait_status(path,limit=4*3600):
    end=time.monotonic()+limit
    while time.monotonic()<end:
        if path.exists():
            state=json.loads(path.read_text())
            if state['status']=='COMPLETE':return state
            if state['status'] not in ['STARTED','RUNNING']:
                raise RuntimeError('Upstream stage stopped: '+str(path))
        time.sleep(2)
    raise RuntimeError('Task wait deadline exceeded; no downstream GPU job started')


def cpu(script):
    subprocess.run([PY,'-u','-B','experiments/TASK010-A/scripts/'+script],cwd=ROOT,check=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--offload-recovery',action='store_true');args=p.parse_args()
    wait_status(TASK/'private'/('full_geo_smoke_r2_plan_STATE.json' if args.offload_recovery else 'full_geo_smoke_plan_STATE.json'))
    smoke=json.loads((TASK/'outputs/geomotion_full'/('night007_dev_smoke_r2' if args.offload_recovery else 'night007_dev_smoke_r1')/'receipt.json').read_text())
    if not smoke.get('strict_model_load') or not smoke['RAFT_native_hidden_equivalence']['PASS']:
        raise RuntimeError('Full GeoMotion official interface not admitted')
    roster=json.loads((TASK/'private/DATA_MANIFEST.json').read_text())
    jobs=[{'id':'full_geomotion_'+d['name']+'_r1','command':[PY,'-u','-B',
        'experiments/TASK010-A/scripts/infer_full_geomotion.py','--dataset',d['name'],*(['--cpu-offload'] if args.offload_recovery else [])]} for d in roster]
    plan=TASK/'private/full_geo_expansion_plan.json'
    if plan.exists():raise RuntimeError('Full expansion plan already exists')
    plan.write_text(json.dumps(jobs,indent=2))
    print('FULL_MODEL_SMOKE_PASS_STARTING_FIXED_NINE_WINDOWS',flush=True)
    subprocess.run([PY,'-u','-B','experiments/TASK010-A/scripts/run_jobs.py','--plan',str(plan)],cwd=ROOT,check=True)
    cpu('seal_prediction_cache.py');cpu('audit_candidate_outputs.py')
    # First preloaded launcher executes an actual readonly observer probe and
    # three Full-model development comparisons, each in a fresh GPU child.
    dev=[{'id':'observer_readonly_probe_r1','script':'experiments/TASK010-A/scripts/observer_readonly_probe.py','args':[]}]
    for seed in [43,44,45]:
        name=f'night007_dev_geomotion_full_s{seed}_r1'
        dev.append({'id':name,'script':'experiments/TASK010-A/scripts/run_window_v2.py',
            'args':['--dataset','night007_dev','--method','geomotion_full','--seed',str(seed),
                '--priors','/mnt/d/aaa/GameCam-VO-TASK009/experiments/TASK009/outputs/native_priors_216x384_r3',
                '--output','experiments/TASK010-A/outputs/droid/'+name]})
    ready=TASK/'private/FORKSERVER_TRANSFER_READY.json'
    if ready.exists():raise RuntimeError('Development forkserver batch already exists')
    ready.write_text(json.dumps({'stage':'Full_detector_development_only','jobs':dev},indent=2))
    wait_status(TASK/'private/forkserver_transfer_STATE.json')
    cpu('evaluate_runs.py');cpu('summarize_experiments.py');cpu('freeze_transfer.py')
    print('CANDIDATES_FROZEN_STARTING_HELDOUT_FRESH_CHILD_COMPARISON',flush=True)
    with (TASK/'private/forkserver_holdout_launcher.log').open('x') as log:
        subprocess.run(['wsl','--exec','sh',
            '/mnt/d/aaa/GameCam-VO-TASK010-A/experiments/TASK010-A/scripts/run_native.sh',
            'experiments/TASK010-A/scripts/native_holdout_controller.py'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    cpu('evaluate_runs.py');cpu('summarize_experiments.py')
    (TASK/'private/CONTINUATION_COMPLETE.json').write_text(json.dumps({'status':'COMPLETE','automatic_retry':False},indent=2))


if __name__=='__main__':main()
