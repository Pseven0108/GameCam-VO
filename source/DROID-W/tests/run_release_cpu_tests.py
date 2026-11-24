"""Retain 118 legacy test identities and add release-fix CPU tests."""
import os
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1'
import json,pathlib,sys,time,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tests import run_native_cpu_tests as original
from tests import test_release_fixes
import torch
def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'initial'
    out=ROOT/'artifacts'/('RELEASE_CPU_'+label);out.mkdir(exist_ok=False)
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(original.test_control),
                             unittest.defaultTestLoader.loadTestsFromModule(original.test_native),
                             unittest.defaultTestLoader.loadTestsFromModule(test_release_fixes)])
    started=time.time()
    with (out/'unittest.stderr.txt').open('x') as log:
        r=unittest.TextTestRunner(stream=log,verbosity=2,resultclass=original.RecordedResult).run(suite)
    rows=original.rows
    report={'scope':'CPU_ONLY_RELEASE_FIXES_NO_NATIVE_C0_OR_MODELS','total':r.testsRun,'passed':sum(x['actual']=='PASS' for x in rows),
            'legacy_118_cases':sum(not x['test_id'].startswith('tests.test_release_fixes.') for x in rows),
            'new_cases':sum(x['test_id'].startswith('tests.test_release_fixes.') for x in rows),
            'failures':len(r.failures),'errors':len(r.errors),'seconds':time.time()-started,
            'cuda_initialized':torch.cuda.is_initialized(),'pretrained_model_constructed':False,'real_RGB_inputs':0,
            'native_C0_created':False,'tests':rows}
    (out/'CPU_TEST_REPORT.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='tests'}))
    for row in rows:
        if row['actual']!='PASS':print(row['test_id']+'\n'+row['stderr'])
    return 0 if r.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
