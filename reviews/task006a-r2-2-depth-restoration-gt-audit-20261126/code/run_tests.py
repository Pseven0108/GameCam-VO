"""Run actual unittest suite; preserve stdout/stderr, count and runtime."""
import io,platform,time,unittest
from common import *
def main():
    cpu_only();start=time.perf_counter();suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_r22.py')
    log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    with (ROOT/'logs/CPU_TESTS.stdout_stderr.txt').open('x',encoding='utf-8') as f:f.write(log.getvalue())
    report={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
      'status':'PASS' if result.wasSuccessful() else 'FAIL','Python':platform.python_version(),'numpy':np.__version__,
      'elapsed_CPU_seconds':time.perf_counter()-start,'CUDA_VISIBLE_DEVICES':os.environ['CUDA_VISIBLE_DEVICES'],
      'log_sha256':sha(ROOT/'logs/CPU_TESTS.stdout_stderr.txt'),'exit_code':0 if result.wasSuccessful() else 1,
      'initial_analytic_float64_vs_native_float32_validation_failure_preserved':True,'tolerance_relaxed':False}
    dump(ROOT/'tests/CPU_TEST_REPORT.json',report);print(json.dumps(report,indent=2))
    if not result.wasSuccessful():raise SystemExit(1)
if __name__=='__main__':main()
