"""Exact historical growth boundaries and real IPC/owned-process integration tests."""
import hashlib,json,os,pathlib,subprocess,sys,time,uuid
from runner_core import GrowthGuard,SafetyStop,supervise_once
from linux_safety import atomic_json

def run(out):
    out=pathlib.Path(out);unit=[]
    cases=[('29_samples_insufficient',[100.+30*i for i in range(29)],False),('30_strictly_growing_gt512',[100.+20*i for i in range(30)],True),('delta_exactly512_allowed',[100.+i for i in range(29)]+[612.],False),('delta_512_001_stops',[100.+i for i in range(29)]+[612.001],True),('delta_below512',[100.+i for i in range(29)]+[611.999],False),('one_equal_step_breaks_strict_growth',[100.+20*i if i!=15 else 380. for i in range(30)],False),('one_decreasing_step_breaks_strict_growth',[100.+20*i if i!=15 else 379. for i in range(30)],False),('constant_30_frames',[100.]*30,False),('rolling_window_after_flat_prefix',[100.]*5+[100.+20*i for i in range(1,31)],True)]
    for name,values,expected in cases:
        g=GrowthGuard();reason=None;at=None
        try:
            for i,v in enumerate(values):g.append(i,v)
        except SafetyStop as e:reason=str(e);at=i
        unit.append({'name':name,'frame_allocated_MiB':values,'expected_growth_stop':expected,'stop_reason':reason,'stop_at_ordinal':at,'passed':(reason is not None)==expected and (reason is None or 'SUSTAINED_MONOTONIC' in reason)})
    for name,index,value,expect in [('duplicate_frame',0,100.,'FRAME_ORDINAL'),('NaN_frame',1,float('nan'),'INVALID_FRAME_ALLOCATED')]:
        g=GrowthGuard();g.append(0,100.);reason=None
        try:g.append(index,value)
        except SafetyStop as e:reason=str(e)
        unit.append({'name':name,'stop_reason':reason,'passed':reason is not None and expect in reason})
    atomic_json(out/'08_memory_growth_guard_tests.json',{'source':'K6-A-GPU-R1/scripts/k6a_safety.py:frame_boundary','window_samples':30,'adjacent_comparison':'all(b > a)','delta_comparison':'last - first > 512 MiB; equality does not stop','tests':unit,'real_GPU_memory_pressure_used':False,'passed':all(x['passed'] for x in unit)})
    cases=[('A_normal','normal',None),('B_CUDA_below512','cuda_low','CUDA_FREE_BELOW_512'),('C_NVML_below512','nvml_low','NVML_FREE_BELOW_512'),('D_CUDA_stops_updating','cuda_stale','CUDA_MONITOR_STALE'),('E_NVML_stops_updating','nvml_stale','NVML_MONITOR_STALE'),('F_monitor_abnormal_exit','monitor_exit','MONITOR_SUBPROCESS_EXITED:17'),('G_30_frame_allocated_growth','growth_30','SUSTAINED_MONOTONIC'),('H_worker_abnormal_exit','worker_exit','WORKER_NONZERO_EXIT:23'),('I_startup_barrier_failure','startup_barrier_stall','NVML_MONITOR_STALE'),('J_GPU_UUID_changes','uuid_drift','GPU_UUID_DRIFT'),('K_CUDA_query_exception','cuda_error','CUDA_QUERY_FAILED'),('L_NVML_query_exception','nvml_error','NVML_QUERY_FAILED'),('M_SIGTERM_grace_then_SIGKILL','ignore_SIGTERM','CUDA_FREE_BELOW_512')]
    results=[];script=pathlib.Path(__file__).parent/'dummy_transport.py';env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
    for name,fault,expected in cases:
        folder=out/'integration_tests'/name;session='launch-audit-dummy-'+str(uuid.uuid4())
        base=[sys.executable,'-B',str(script),'--out',str(folder),'--session',session,'--fault',fault]
        result=supervise_once(folder,session,base+['--role','worker'],base+['--role','nvml'],'cpu_dummy',env=env,expected_frames=3 if fault=='normal' else None)
        passed=result['passed'] if expected is None else (expected in (result['reason'] or '') and result['worker_fully_exited'] and result['monitor_fully_exited'])
        if fault=='ignore_SIGTERM':passed=passed and result['worker_stop']['signals']==['SIGTERM','SIGKILL'] and result['worker_exit_code']==-9 and result['worker_stop']['signal_to_exit_seconds']>=5
        if fault=='startup_barrier_stall':passed=passed and not result['worker_started'] and not result['work_permit_written']
        row={'case':name,'fault':fault,'expected_reason':expected,'supervisor_result':result,'passed':bool(passed)};results.append(row)
        print(json.dumps({'integration_case':name,'passed':bool(passed),'reason':result['reason']}),flush=True)
    data={'scope':'Production supervise_once with independent CPU dummy worker and independent CPU mock NVML producer, actual files/timestamps/session checks and OS process groups','model_execution_authorized':False,'model_attempt_limit':0,'model_attempts':0,'real_GPU_computation':False,'real_images_decoded':False,'checkpoint_deserialized':False,'GT_values_read':False,'tests':results,'all_owned_processes_exited':all(r['supervisor_result']['worker_fully_exited'] and r['supervisor_result']['monitor_fully_exited'] for r in results),'passed':all(x['passed'] for x in results)}
    atomic_json(out/'07_supervisor_integration_tests.json',data);return data
if __name__=='__main__':raise SystemExit(0 if run(sys.argv[1])['passed'] else 2)