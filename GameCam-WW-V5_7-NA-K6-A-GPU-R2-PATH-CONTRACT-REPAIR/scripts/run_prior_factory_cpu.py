import os,sys,pathlib,subprocess,json,time,hashlib
A=pathlib.Path(os.environ.get('CPU_AUDIT','/root/rivermind-data/gamecam/prior-model-factory-cpu-preflight-20261109T160007Z'));R=pathlib.Path(os.environ.get('CPU_WORKTREE','/root/rivermind-data/gamecam/staging/GameCam-VO-Prior-Factory-20261109T160007Z'));S=R/'GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts';P='/opt/gamecam/envs/droidw-cu126/bin/python';sys.path.insert(0,str(S))
from ipc_runtime import prepare_owner,cleanup_owner
from runner_core import supervise_once
fault=sys.argv[1] if len(sys.argv)>1 else 'none';tag=sys.argv[2] if len(sys.argv)>2 else str(time.time_ns());supervised='--supervised' in sys.argv
candidate=pathlib.Path(os.environ.get('CPU_CANDIDATE',str(A/'cpu_probe_candidate.json')))
safe_fault=fault.replace(':','_').replace('.','_');out=A/('cpu-factory-'+safe_fault+'-'+tag);sid=out.name
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(S));env.pop('PYTHONPYCACHEPREFIX',None)
cmd=[P,'-B',str(S/'prior_factory_production_child_cpu_fixture.py'),'--candidate',str(candidate),'--out',str(out),'--fault',fault]
t=time.monotonic()
if supervised:
 # CPU fixture preserves the real diagnostic Terminal schema and validation.
 # Only the supervisor's test execution-kind routing is adapted in memory.
 import worker_terminal
 original_read_terminal=worker_terminal.read_terminal
 worker_terminal.read_terminal=lambda folder,session,pid,kind:original_read_terminal(folder,session,pid,'droidw_diagnostic')
 monitor=[P,'-B',str(S/'dummy_transport.py'),'--role','nvml','--out',str(out),'--session',sid,'--fault','nvml_stale' if fault=='timeout' else 'normal']
 r=supervise_once(out,sid,cmd+['--supervised'],monitor,'cpu_dummy',env=env,expected_frames=0,ipc_for_cpu_tests=True,startup_for_cpu_tests=True);rc=r.get('worker_exit_code');clean=r.get('ipc_cleanup')
else:
 out.mkdir(mode=0o700);owner=prepare_owner(out,sid)
 try:
  p=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=600);rc=p.returncode;(out/'worker.stdout.log').write_text(p.stdout);(out/'worker.stderr.log').write_text(p.stderr)
 finally:clean=cleanup_owner(owner,True,True,[])
 r=None
report=dict(fault=fault,CPU_only=True,supervised=supervised,candidate=str(candidate),elapsed_seconds=time.monotonic()-t,exit_code=rc,cleanup=clean,supervisor=r,out=str(out))
for name in ('CPU_PRIOR_FACTORY_RESULT.json','result.json'):
 f=out/'model'/name
 if f.exists():report[name]=json.loads(f.read_text())
(A/('RESULT_'+safe_fault+'_'+tag+'.json')).write_text(json.dumps(report,indent=2));print(json.dumps(dict(out=str(out),fault=fault,exit_code=rc,elapsed_seconds=report['elapsed_seconds'],passed=(report.get('CPU_PRIOR_FACTORY_RESULT.json') or {}).get('status'),cleanup_passed=clean.get('passed') if clean else None,supervisor_reason=r.get('reason') if r else None)))
