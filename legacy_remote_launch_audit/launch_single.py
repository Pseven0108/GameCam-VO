"""The only launch command. Current default is a CPU dry run; execution needs a separate exact-contract authorization."""
import argparse,json,os,pathlib,sys,time,uuid,shutil
from launch_contract import *
from linux_safety import atomic_json,EXPECTED_UUID
from runner_core import supervise_once

def dry_run(output):
    candidate=validate_candidate(AUDIT/'10_launch_contract_candidate.json');a=frozen_artifacts();cfg=a['cfg'];checks={
      'frozen_Python':str(pathlib.Path(sys.prefix).resolve())=='/opt/gamecam/envs/droidw-cu126','project_realpath':ROOT.resolve()==ROOT,'input_realpath':pathlib.Path(cfg['data']['input_folder']).resolve().is_relative_to(ROOT/'GameCam-WW-V5_7-NA-K4'),'output_matches_frozen_config':cfg['data']['output']==str(FUTURE_ROOT/'runs/droidw/V56_01_middle'),'future_model_stage_not_created':not FUTURE_ROOT.exists(),'original_config_SHA':a['config']['original_sha256']==ORIGINAL_SHA,'prepared_config_SHA':a['config']['prepared_sha256']==PREPARED_SHA,'four_checkpoint_SHA':a['weights']['passed'],'input120_SHA':a['input']['passed'],'production_supervisor_integration':load(AUDIT/'07_supervisor_integration_tests.json')['passed'],'growth_guard_boundaries':load(AUDIT/'08_memory_growth_guard_tests.json')['passed'],'GT_isolation_proven':load(AUDIT/'02_GT_isolation_verification.json')['passed'],'authorization_false':candidate['model_execution_authorized'] is False,'model_attempt_limit_zero':candidate['model_attempt_limit']==0,'no_torch_import':'torch' not in sys.modules,'data_disk_at_least20percent_free':shutil.disk_usage('/root/rivermind-data').free/shutil.disk_usage('/root/rivermind-data').total>=.2,'GPU_readonly_identity_verified':load(AUDIT/'readonly_GPU_identity.json')['passed']}
    # Exercise exclusive single-use claims only in a disposable CPU fixture, never the future model stage.
    fixture=AUDIT/'dry_run_fixture';fixture.mkdir(exist_ok=False);marker=fixture/'cpu_only_single_use_marker.json';claim_once(marker,{'scope':'CPU lifecycle test','model_attempts':0})
    second_rejected=False
    try:claim_once(marker,{'scope':'must never replace first marker'})
    except FileExistsError:second_rejected=True
    checks['exclusive_single_use_second_claim_rejected']=second_rejected
    result={'scope':'CPU command/config/input/weights/monitor/lifecycle validation only','checks':checks,'python':sys.executable,'only_future_model_command':[sys.executable,'-B',str(AUDIT/'scripts/launch_single.py'),'--execute','--authorization','<future_user_authorization.json>'],'model_child_command_template':[sys.executable,'-B',str(AUDIT/'scripts/native_child.py'),'--authorization','<future_user_authorization.json>','--session-dir','<owned_session_dir>','--session','<session_uuid>'],'NVML_command_template':[sys.executable,'-B',str(AUDIT/'scripts/linux_safety.py'),'--monitor','<owned_session_dir>','--session','<session_uuid>'],'GPU_UUID':EXPECTED_UUID,'raw_weight_bytes_hashed_without_deserialization':True,'real_images_decoded':False,'GT_values_read':False,'model_execution_authorized':False,'model_attempt_limit':0,'model_attempts':0,'model_child_spawned':False,'future_output_created':False,'passed':all(checks.values())}
    atomic_json(output,result);print(json.dumps({'dry_run_passed':result['passed'],'model_attempts':0,'torch_imported':False}),flush=True);return 0 if result['passed'] else 2

def execute(authorization):
    require_authorization(AUDIT/'10_launch_contract_candidate.json',authorization)
    a=frozen_artifacts();assert not FUTURE_ROOT.exists(),'Prior attempt or output exists; no replay'
    FUTURE_ROOT.mkdir(exist_ok=False);session='droidw-r2-'+str(uuid.uuid4())
    claim_once(FUTURE_ROOT/'model_attempt.json',{'attempt_number':1,'session':session,'contract_sha256':sha(AUDIT/'10_launch_contract_candidate.json'),'method':'droidw','case':'V56_01_middle','max_frames':120,'automatic_retry':False})
    folder=FUTURE_ROOT/'supervisor_session';env=dict(os.environ,CUDA_VISIBLE_DEVICES='0',PYTHONDONTWRITEBYTECODE='1',GAMECAM_SUPERVISOR_PID=str(os.getpid()))
    worker=[sys.executable,'-B',str(AUDIT/'scripts/native_child.py'),'--authorization',str(pathlib.Path(authorization).resolve()),'--session-dir',str(folder),'--session',session]
    monitor=[sys.executable,'-B',str(AUDIT/'scripts/linux_safety.py'),'--monitor',str(folder),'--session',session]
    result=supervise_once(folder,session,worker,monitor,'droidw',env=env,expected_frames=120)
    return 0 if result['passed'] else 2
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--dry-run',action='store_true');g.add_argument('--execute',action='store_true');p.add_argument('--out-json');p.add_argument('--authorization');args=p.parse_args()
    try:code=dry_run(args.out_json or str(AUDIT/'09_droidw_dry_run.json')) if args.dry_run else execute(args.authorization)
    except BaseException as exc:
        print(json.dumps({'status':'LAUNCH_REJECTED','reason':str(exc),'model_attempts':0,'torch_imported':'torch' in sys.modules,'model_constructed':False}),flush=True);code=3
    raise SystemExit(code)