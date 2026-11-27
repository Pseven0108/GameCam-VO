"""Run A7 CPU tests and exact inherited regression tests in separate processes.

The inherited test asserts torch is not imported; A7 adapter tests deliberately
use CPU torch. Separate processes keep these contracts both meaningful.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from common import PARENT, ROOT, TASK, dump, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt',default='results_002')
    args = parser.parse_args()
    if '/' in args.attempt or '\\' in args.attempt:
        raise ValueError('Attempt must be a single task-local directory name')
    out = TASK/'tests'/args.attempt
    out.mkdir(exist_ok=False)
    # This fixture was published in the reviewed fixed commit but not mirrored
    # in its top-level task directory. Materialize EXACT bytes, no new metric.
    rel = 'reviews/task011b-validity-aware-cadp-dr-20261127/reproducibility/experiments/TASK011B/intake/reliability_metrics_frozen.py'
    raw = subprocess.check_output(['git','show',PARENT+':'+rel],cwd=ROOT)
    fixture = ROOT/'experiments/TASK011B/intake/reliability_metrics_frozen.py'
    fixture.parent.mkdir(parents=True,exist_ok=True)
    if fixture.exists() and fixture.read_bytes() != raw:
        raise RuntimeError('Preserve unexpected inherited fixture')
    fixture.write_bytes(raw)
    regression_rel = 'reviews/task011b-validity-aware-cadp-dr-20261127/reproducibility/experiments/TASK011B/intake/NATIVE_REGRESSION_FORMAL_REAL_FIRST_LOCAL.json'
    regression_raw = subprocess.check_output(['git','show',PARENT+':'+regression_rel],cwd=ROOT)
    regression = fixture.with_name('NATIVE_REGRESSION_FORMAL_REAL_FIRST_LOCAL.json')
    if regression.exists() and regression.read_bytes() != regression_raw:
        raise RuntimeError('Preserve unexpected inherited native-regression receipt')
    regression.write_bytes(regression_raw)
    env = dict(os.environ,CUDA_VISIBLE_DEVICES='-1',PYTHONDONTWRITEBYTECODE='1',
               TMP='D:/aaa/tmp/gamecam-vo',TEMP='D:/aaa/tmp/gamecam-vo')
    groups = [('A7_CPU_CONTRACTS',TASK/'tests'),('FROZEN_TASK011B_REGRESSIONS',ROOT/'experiments/TASK011B/tests')]
    results = []
    code = """
import json,os,sys,time,unittest
start=time.perf_counter()
suite=unittest.defaultTestLoader.discover(sys.argv[1],pattern='test_*.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
imported=sys.modules.get('torch')
state=dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
           skipped=len(result.skipped),was_successful=result.wasSuccessful(),
           seconds=time.perf_counter()-start,CUDA_VISIBLE_DEVICES=os.environ['CUDA_VISIBLE_DEVICES'],
           torch_imported=imported is not None,CUDA_initialized=bool(imported and imported.cuda.is_initialized()),
           model_inference=False,synthetic_CPU_only=True)
print('CPU_TEST_RECEIPT='+json.dumps(state))
sys.exit(0 if result.wasSuccessful() and not state['CUDA_initialized'] else 1)
"""
    for name, folder in groups:
        proc = subprocess.run([sys.executable,'-B','-c',code,str(folder)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
        (out/(name+'.stdout.txt')).write_text(proc.stdout,encoding='utf-8')
        (out/(name+'.stderr.txt')).write_text(proc.stderr,encoding='utf-8')
        receipt = next((x[len('CPU_TEST_RECEIPT='):] for x in proc.stdout.splitlines() if x.startswith('CPU_TEST_RECEIPT=')),None)
        result = json.loads(receipt) if receipt else dict(was_successful=False,receipt_missing=True)
        result.update(group=name,exit_code=proc.returncode)
        results.append(result)
        dump(out/(name+'.json'),result)
    passed = all(r['was_successful'] and r['exit_code']==0 for r in results)
    summary = dict(status='PASS' if passed else 'FAIL',groups=results,
                   tests_run=sum(r.get('tests_run',0) for r in results),
                   fixture_source_parent=PARENT,fixture_source_path=rel,fixture_sha256=sha(fixture),
                   native_regression_receipt_source=regression_rel,native_regression_receipt_sha256=sha(regression),
                   GPU_equivalence='NOT_TESTED',models_loaded=0,CUDA_initializations=0)
    dump(out/'CPU_TEST_SUMMARY.json',summary)
    print(json.dumps(summary))
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
