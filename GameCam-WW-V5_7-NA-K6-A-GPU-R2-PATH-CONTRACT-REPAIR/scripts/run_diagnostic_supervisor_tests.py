"""Real subprocess lifecycle tests with synthetic samples and in-memory mock context."""
import argparse,json,os,pathlib,sys,time,hashlib
from runner_core import supervise_once
from diagnostic_authorization import verify_terminal_result
from ipc_runtime import expected_root
p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();base=pathlib.Path(a.output);base.mkdir(parents=True,exist_ok=False);rows=[]
class MockContext:
    claimed=False
    def __init__(self,session):self._candidate={'planned_ipc_root':str(expected_root(session))}
    def validate(self,*args,consume=False,**kwargs):
        if consume:self.claimed=True
    def validate_terminal(self,out,terminal):verify_terminal_result(json.loads((pathlib.Path(out)/'model/result.json').read_text()),terminal)
for index,fault in enumerate(['normal','terminal_delay','scope_escape','low_memory','cuda_stale','nvml_stale','crash','terminal_hang']):
    session='MOCK_DIAGNOSTIC_'+str(os.getpid())+'_'+str(index);out=base/fault;script=str(pathlib.Path(__file__).with_name('diagnostic_fake_worker.py'))
    command=lambda role:[sys.executable,'-B',script,'--role',role,'--out',str(out),'--session',session,'--fault',fault]
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1');ctx=MockContext(session)
    r=supervise_once(out,session,command('worker'),command('monitor'),'droidw_diagnostic',env=env,expected_frames=0,launch_context=ctx)
    passed=r['passed'] if fault in ('normal','terminal_delay') else not r['passed']
    passed=passed and r['worker_fully_exited'] and r['monitor_fully_exited'] and r['ipc_cleanup']['passed'] and not expected_root(session).exists()
    rows.append(dict(fault=fault,passed=passed,result=r));print(json.dumps(rows[-1]),flush=True)
report=dict(status='PASS' if all(r['passed'] for r in rows) else 'FAIL',tests=len(rows),passed=sum(r['passed'] for r in rows),synthetic_only=True,real_model_loaded=False,results=rows)
(base/'report.json').write_text(json.dumps(report,indent=2));raise SystemExit(0 if report['status']=='PASS' else 2)
