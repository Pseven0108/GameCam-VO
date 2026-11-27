"""Prepare permitted CPU evidence while the single remote GPU supervisor runs.

This never launches a GPU process, changes the experiment or publishes a partial
report. Final packaging and public publication still follow actual final QA.
"""
import json,os,subprocess,sys,time
from common import TASK,dump


def run(name,*args):
    p=subprocess.run([sys.executable,'-u','-B',str(TASK/'scripts'/name),*args],
        capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    print(p.stdout.decode(errors='replace'),end='',flush=True)
    if p.returncode:
        print(p.stderr.decode(errors='replace')[-6000:],flush=True)
        raise RuntimeError('CPU evidence step failed: '+name)


def main():
    previous=-1
    while not (TASK/'gpu_results/BATCH_COMPLETE.json').exists():
        count=len(list((TASK/'gpu_results/receipts').glob('window_*.json')))
        if count>=7 and count//7>previous:
            previous=count//7
            run('evaluate_viper.py','--partial')
            run('analyze_gpu_mechanisms.py')
            run('stage_gpu_review_evidence.py','--partial')
            print('CPU_EVIDENCE_CHECKPOINT',count,flush=True)
        time.sleep(25)
    run('evaluate_viper.py')
    run('analyze_gpu_mechanisms.py')
    run('stage_gpu_review_evidence.py')
    run('summarize_runtime_resources.py')
    run('audit_formal_runs.py')
    run('plot_viper_results.py')
    dump(TASK/'private/CPU_EVIDENCE_READY.json',dict(status='ACTUAL_140_OUTCOME_EVIDENCE_READY',
        GPU_experiments_started_by_this_script=0,publication_started=False,
        final_visual_QA_and_protection_and_review_required=True))
    print('ALL_CPU_EVIDENCE_READY_FOR_FINAL_QA',flush=True)


if __name__=='__main__':main()
