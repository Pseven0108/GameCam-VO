"""No-model validation of the exact stage authorization guard."""
import json,os,pathlib,sys,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
from control_common import ControlError
from native_control import stage_authorization as grant
from native_control.stages import mode_spec
OUT=pathlib.Path(sys.argv[1]);OUT.mkdir(parents=True,exist_ok=True)
REAL=pathlib.Path(os.environ['GAMECAM_NATIVE_WORKSPACE'])
class GrantTests(unittest.TestCase):
    def fixture(self,name):
        r=OUT/name;r.mkdir();(r/'authorization').mkdir();(r/'evidence').mkdir();(r/'source_candidate/native_control').mkdir(parents=True)
        (r/'authorization/TASK_REQUEST.txt').write_bytes((REAL/'authorization/TASK_REQUEST.txt').read_bytes())
        (r/'evidence/CPU_STAGE_RELEASE.json').write_text(json.dumps({'candidate_commit':'C'}))
        out=r/'attempts/restore_check';out.mkdir(parents=True)
        doc={'spec':mode_spec('restore_check'),'source_commit':'C','child_token':'TOKEN'}
        (out/'LAUNCH_INTENT.json').write_text(json.dumps(doc))
        env={'GAMECAM_NATIVE_WORKSPACE':str(r),'GAMECAM_NATIVE_APPROVED_MODE':'restore_check','GAMECAM_NATIVE_INTERNAL_CHILD':'TOKEN','GAMECAM_NATIVE_SOURCE_COMMIT':'C','GAMECAM_NATIVE_ATTEMPT':str(out)}
        return r,out,doc,env,SimpleNamespace(arm='E0',campaign='FACTORIAL',local_dwu=(1,1,1),final_phases=2)
    def invoke(self,name,mutate=lambda r,o,d,e,a:None,success=False):
        r,o,d,e,a=self.fixture(name);mutate(r,o,d,e,a)
        (o/'LAUNCH_INTENT.json').write_text(json.dumps(d))
        with patch.dict(os.environ,e),patch.object(grant,'__file__',str(r/'source_candidate/native_control/stage_authorization.py')):
            if success:self.assertIs(grant.validate_runtime(a),a)
            else:
                with self.assertRaises(ControlError):grant.validate_runtime(a)
    def test_exact_stage_grant(self):self.invoke('valid',success=True)
    def test_wrong_child_token(self):self.invoke('token',lambda r,o,d,e,a:e.update(GAMECAM_NATIVE_INTERNAL_CHILD='wrong'))
    def test_wrong_source(self):self.invoke('source',lambda r,o,d,e,a:e.update(GAMECAM_NATIVE_SOURCE_COMMIT='wrong'))
    def test_wrong_stage_bound(self):self.invoke('bound',lambda r,o,d,e,a:d['spec'].update(max_rgb=487))
    def test_changed_authorization(self):self.invoke('auth',lambda r,o,d,e,a:(r/'authorization/TASK_REQUEST.txt').write_text('changed'))
    def test_wrong_baseline_policy(self):self.invoke('policy',lambda r,o,d,e,a:setattr(a,'local_dwu',(0,1,1)))
if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GrantTests))
    d={'scope':'CPU_STAGE_AUTHORIZATION_GUARD','total':r.testsRun,'passed':r.testsRun-len(r.errors)-len(r.failures),'failures':len(r.failures),'errors':len(r.errors),'CUDA_used':False}
    (OUT/'STAGE_GUARD_CPU_REPORT.json').write_text(json.dumps(d,indent=2));print(json.dumps(d));sys.exit(0 if r.wasSuccessful() else 1)
