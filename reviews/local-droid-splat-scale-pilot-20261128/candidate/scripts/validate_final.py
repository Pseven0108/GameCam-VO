import json,pathlib,unittest
TASK=pathlib.Path(__file__).resolve().parents[1]
suite=unittest.defaultTestLoader.discover(str(TASK/'tests'),pattern='test_*.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
out=TASK/'reports/FINAL_CPU_TEST_RESULTS.json'
if out.exists():raise FileExistsError(out)
out.write_text(json.dumps(dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
    skipped=len(result.skipped),successful=result.wasSuccessful(),scope='synthetic CPU contracts and offline metric checks'),indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
