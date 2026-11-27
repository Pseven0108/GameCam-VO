"""Finish evidence-only checks after the existing one GPU batch completes.

Never launches a model, changes a protocol, publishes or starts a next stage.
Final visible figure inspection and publication remain explicit final steps.
"""
import json,os,subprocess,sys,time
from common import TASK,dump


def run(script):
    p=subprocess.run([sys.executable,'-u','-B',str(TASK/'scripts'/script)],capture_output=True,
        env=dict(os.environ,CUDA_VISIBLE_DEVICES='-1',PYTHONDONTWRITEBYTECODE='1'))
    print(p.stdout.decode(errors='replace'),end='',flush=True)
    if p.returncode:
        print(p.stderr.decode(errors='replace')[-5000:],flush=True)
        raise RuntimeError('Final CPU evidence check failed: '+script)


def main():
    gate=TASK/'private/CPU_EVIDENCE_READY.json'
    while not gate.exists():time.sleep(25)
    if not (TASK/'gpu_results/BATCH_COMPLETE.json').exists():raise RuntimeError('GPU completion evidence missing')
    for script in ('collect_final_service_logs.py','analyze_input_conditions.py','analyze_geometry_increment.py',
                   'analyze_run_costs.py','analyze_motion_strata.py','plot_motion_sensitivity.py'):
        run(script)
    # Recreate the final complete original plots with the final failed-arm
    # annotation. No CSV or score implementation is changed by this export.
    run('plot_viper_results.py')
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='-1',PYTHONDONTWRITEBYTECODE='1')
    env['PYTHONPATH']=str(TASK/'scripts')+os.pathsep+str(TASK/'CADP_DR_EXPERIMENTAL_BRANCH')
    tests=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(TASK/'tests'),'-v'],
        capture_output=True,env=env)
    log=TASK/'private/CPU_TESTS_FINAL.log'
    if log.exists():raise FileExistsError('Preserve previous final-test evidence')
    log.write_bytes(tests.stdout+tests.stderr)
    if tests.returncode:raise RuntimeError('Final CPU tests failed; see saved original log')
    print('FINAL_CPU_TESTS_PASSED',flush=True)
    run('verify_final_protection.py')
    dump(TASK/'private/FINAL_CPU_CHECKS_READY.json',dict(
        status='ALL_EVIDENCE_ONLY_CHECKS_COMPLETE_WAITING_FOR_VISIBLE_QA',
        actual_GPU_batch_outcomes=140,models_started=0,published=False,
        next_stage_started=False,visual_inspection_required=True))
    print('FINAL_CPU_CHECKS_READY_FOR_VISUAL_QA_AND_REVIEW',flush=True)


if __name__=='__main__':main()
