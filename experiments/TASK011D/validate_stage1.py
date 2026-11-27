"""Sequential acceptance: legacy 122, new CPU, synthetic CUDA, runtime audit."""
import argparse,importlib.util,json,os,subprocess,sys,time
from pathlib import Path
from common import ROOT,TASK,dump

LOG_ROOT=TASK/'reports/test_logs'
def run_group(name,directory,pattern,device,redirect=False):
    folder=LOG_ROOT;folder.mkdir(parents=True,exist_ok=True)
    if (folder/(name+'.json')).exists():raise FileExistsError('Preserve earlier test receipt')
    code='''import importlib.util,json,os,sys,time,unittest
if REDIRECT:
 p=ADAPTER
 spec=importlib.util.spec_from_file_location('uniform_control',p)
 m=importlib.util.module_from_spec(spec);sys.modules['uniform_control']=m;spec.loader.exec_module(m)
suite=unittest.defaultTestLoader.discover(DIRECTORY,pattern=PATTERN)
t=time.perf_counter();result=unittest.TextTestRunner(verbosity=2).run(suite)
torch=sys.modules.get('torch')
x=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),passed=result.wasSuccessful(),seconds=time.perf_counter()-t,CUDA_initialized=bool(torch and torch.cuda.is_initialized()),research_models_loaded=False)
print('RECEIPT='+json.dumps(x));sys.exit(0 if x['passed'] and not x['skipped'] else 1)
'''.replace('REDIRECT',repr(redirect)).replace('ADAPTER',repr(str(TASK/'uniform_control.py'))).replace('DIRECTORY',repr(str(directory))).replace('PATTERN',repr(pattern))
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='0' if device=='cuda' else '-1',PYTHONDONTWRITEBYTECODE='1',TMP='D:/aaa/tmp/gamecam-vo',TEMP='D:/aaa/tmp/gamecam-vo')
    p=subprocess.run([sys.executable,'-B','-c',code],cwd=ROOT,env=env,capture_output=True,text=True,timeout=180)
    (folder/(name+'.stdout.txt')).write_text(p.stdout,encoding='utf-8');(folder/(name+'.stderr.txt')).write_text(p.stderr,encoding='utf-8')
    data=next((s[8:] for s in p.stdout.splitlines() if s.startswith('RECEIPT=')),None)
    r=json.loads(data) if data else dict(passed=False,error='NO_RECEIPT')
    r.update(name=name,device=device,exit_code=p.returncode);dump(folder/(name+'.json'),r)
    if p.returncode or not r['passed']:raise RuntimeError('Stage1 stopped on '+name)
    return r

def main():
    global LOG_ROOT
    p=argparse.ArgumentParser();p.add_argument('--attempt',default='test_logs_002');a=p.parse_args()
    if '/' in a.attempt or '\\' in a.attempt:raise ValueError('Task-local attempt name required')
    LOG_ROOT=TASK/'reports'/a.attempt
    # Original tests are not edited. The 56 adapter regressions additionally
    # target the new module by import substitution in an isolated CPU process.
    old=Path('D:/aaa/GameCam-VO-TASK011C/experiments')
    groups=[run_group('legacy_C_56_on_D_adapter',old/'TASK011C/tests','test_*.py','cpu',True),
            run_group('legacy_B_66_unchanged',old/'TASK011B/tests','test_*.py','cpu'),
            run_group('new_CPU',TASK/'tests','test_uniform_cpu.py','cpu'),
            run_group('new_source_CPU',TASK/'tests','test_source_gather.py','cpu'),
            run_group('new_CUDA',TASK/'tests','test_uniform_cuda.py','cuda'),
            run_group('D2H_runtime_audit',TASK/'tests','test_no_full_buffer_d2h.py','cuda')]
    dump(TASK/'reports/STAGE1_TEST_RESULTS.json',dict(status='PASS',groups=groups,total_tests=sum(r['tests'] for r in groups),formal_SLAM_runs=0,model_forwards=0))
    print(json.dumps(groups))

if __name__=='__main__':main()
