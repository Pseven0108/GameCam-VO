"""One CPU-only suite, with per-test output, exit status, and byte hashes."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import contextlib,hashlib,io,json,pathlib,sys,time,traceback,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch
assert not torch.cuda.is_initialized()
def forbidden(*args,**kwargs):raise RuntimeError('CUDA_INIT_FORBIDDEN_IN_CPU_SYNTHETIC_TESTS')
torch.cuda._lazy_init=forbidden
from control_common import file_sha,require_space
from tests import test_control
class RecordedResult(unittest.TextTestResult):
    def startTest(self,test):
        self.start=time.perf_counter();self.capture_out=io.StringIO();self.capture_err=io.StringIO();self.out_cm=contextlib.redirect_stdout(self.capture_out);self.err_cm=contextlib.redirect_stderr(self.capture_err);self.out_cm.__enter__();self.err_cm.__enter__();self.outcome='PASS';self.detail=''
        super().startTest(test)
    def addFailure(self,t,err):self.outcome='FAIL';self.detail=self._exc_info_to_string(err,t);super().addFailure(t,err)
    def addError(self,t,err):self.outcome='ERROR';self.detail=self._exc_info_to_string(err,t);super().addError(t,err)
    def stopTest(self,test):
        self.err_cm.__exit__(None,None,None);self.out_cm.__exit__(None,None,None)
        ident=test.id();stdout=self.capture_out.getvalue();stderr=self.capture_err.getvalue()+self.detail
        evidence={'test_id':ident,'seed':43,'input':'small CPU synthetic state / toy events / frozen config only',
            'expected':'assertions pass or specified invalid input rejected','actual':self.outcome,'exit_code':0 if self.outcome=='PASS' else 1,
            'duration_seconds':time.perf_counter()-self.start,'stdout':stdout,'stderr':stderr,
            'stdout_sha256':hashlib.sha256(stdout.encode()).hexdigest(),'stderr_sha256':hashlib.sha256(stderr.encode()).hexdigest(),
            'cuda_initialized':torch.cuda.is_initialized()}
        rows.append(evidence);super().stopTest(test)
rows=[]
if __name__=='__main__':
    out=ROOT/'artifacts/cpu_test_results';out.mkdir(parents=True,exist_ok=False);require_space(out,16*1024**2)
    suite=unittest.defaultTestLoader.loadTestsFromModule(test_control);start=time.time()
    with (out/'unittest.stderr.txt').open('w') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2,resultclass=RecordedResult).run(suite)
    report={'scope':'CPU_SYNTHETIC_ONLY_NOT_NATIVE_DROID','total':result.testsRun,'passed':sum(r['actual']=='PASS' for r in rows),'failures':len(result.failures),'errors':len(result.errors),'duration_seconds':time.time()-start,'cuda_initialized':torch.cuda.is_initialized(),'tests':rows}
    (out/'CPU_TEST_REPORT.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='tests'}))
    (out/'OUTPUT_SHA256.json').write_text(json.dumps({p.name:file_sha(p) for p in out.iterdir() if p.is_file()},indent=2))
    sys.exit(0 if result.wasSuccessful() else 1)
