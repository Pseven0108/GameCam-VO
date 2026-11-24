"""Original 54 tests plus native interface fixtures; never claim GPU success."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import contextlib,hashlib,io,json,pathlib,sys,time,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch
assert not torch.cuda.is_initialized()
def forbidden(*a,**k):raise RuntimeError('CUDA_INITIALIZATION_FORBIDDEN_IN_CPU_INTERFACE_TESTS')
torch.cuda._lazy_init=forbidden
from tests import test_control,test_native
rows=[]
class RecordedResult(unittest.TextTestResult):
    def startTest(self,test):
        self.started=time.perf_counter();self.o=io.StringIO();self.e=io.StringIO()
        self.oc=contextlib.redirect_stdout(self.o);self.ec=contextlib.redirect_stderr(self.e);self.oc.__enter__();self.ec.__enter__()
        self.actual='PASS';self.detail='';super().startTest(test)
    def addFailure(self,test,err):self.actual='FAIL';self.detail=self._exc_info_to_string(err,test);super().addFailure(test,err)
    def addError(self,test,err):self.actual='ERROR';self.detail=self._exc_info_to_string(err,test);super().addError(test,err)
    def stopTest(self,test):
        self.ec.__exit__(None,None,None);self.oc.__exit__(None,None,None)
        stdout=self.o.getvalue();stderr=self.e.getvalue()+self.detail
        rows.append({'test_id':test.id(),'seed':43,'input':'CPU fixtures; actual native Python bodies where indicated; no pretrained model',
                     'expected':'assertions pass, invalid state fails closed','actual':self.actual,'exit_code':0 if self.actual=='PASS' else 1,
                     'seconds':time.perf_counter()-self.started,'stdout':stdout,'stderr':stderr,
                     'stdout_sha256':hashlib.sha256(stdout.encode()).hexdigest(),'stderr_sha256':hashlib.sha256(stderr.encode()).hexdigest(),
                     'cuda_initialized':torch.cuda.is_initialized()})
        super().stopTest(test)

def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'initial'
    out=ROOT/'artifacts'/('CPU_SUITE_'+label);out.mkdir(parents=True,exist_ok=False)
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(test_control),unittest.defaultTestLoader.loadTestsFromModule(test_native)])
    started=time.time()
    with (out/'unittest.stderr.txt').open('x') as f:
        result=unittest.TextTestRunner(stream=f,verbosity=2,resultclass=RecordedResult).run(suite)
    report={'scope':'CPU_NATIVE_INTERFACE_AND_SYNTHETIC_REGRESSION_NOT_GPU','total':result.testsRun,'passed':sum(x['actual']=='PASS' for x in rows),
        'failures':len(result.failures),'errors':len(result.errors),'seconds':time.time()-started,'cuda_initialized':torch.cuda.is_initialized(),
        'pretrained_model_constructed':False,'synthetic_nn_fixture_constructed':True,'native_gpu_runs':0,'tests':rows}
    (out/'CPU_TEST_REPORT.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='tests'}))
    for x in rows:
        if x['actual']!='PASS':print(x['test_id']+'\n'+x['stderr'])
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
