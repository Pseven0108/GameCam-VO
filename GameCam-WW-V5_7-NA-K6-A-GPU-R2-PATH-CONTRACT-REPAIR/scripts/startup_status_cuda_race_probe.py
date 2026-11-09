"""Deterministic first-CUDA/status read race in the actual Supervisor loop."""
import os,sys,time,json,pathlib,threading
from linux_safety import read_json as actual_read
import runner_core
A=pathlib.Path(sys.argv[1]);S=pathlib.Path(__file__).parent;P=sys.executable;out=A/'status-cuda-race';sid='CPU_STATUS_CUDA_RACE'
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
interleaving=[];held=False
def racing_read(p):
 global held
 p=pathlib.Path(p)
 if p.name=='worker_startup.latest.json' and not held and p.is_file():
  value=actual_read(p)
  if value['phase']=='WORKER_IMPORTING':
   held=True;start=time.monotonic()
   while not (out/'cuda.latest.json').exists():
    if time.monotonic()-start>5:raise RuntimeError('RACE_TEST_SETUP_TIMEOUT')
    time.sleep(.005)
   interleaving.append(dict(action='return_older_status_after_CUDA_publication',returned_phase=value['phase'],disk_phase=actual_read(p)['phase'],monotonic_time=time.monotonic()))
   return value
 return actual_read(p)
runner_core.read_json=racing_read
common=[P,'-B',str(S/'startup_fake_worker.py'),'--out',str(out),'--session',sid,'--delay','.5']
r=runner_core.supervise_once(out,sid,common+['--role','worker'],common+['--role','monitor'],'cpu_dummy',env=env,expected_frames=0,ipc_for_cpu_tests=True,startup_for_cpu_tests=True)
assert interleaving,'no race was exercised'
(A/'STATUS_CUDA_INTERLEAVING_TEST.json').write_text(json.dumps(dict(passed=r['passed'],interleaving=interleaving,result=r),indent=2));print(r['passed'],r['reason'])
