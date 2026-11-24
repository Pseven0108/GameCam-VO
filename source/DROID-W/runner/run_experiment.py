"""Safe planning/validation CLI; no real model dispatcher in this release."""
import argparse,json,os,pathlib,sys,uuid
ROOT=pathlib.Path(os.environ.get('GAMECAM_NATIVE_WORKSPACE',pathlib.Path(__file__).absolute().parents[1]))
sys.path.insert(0,str(ROOT))
from control_common import ControlError,require_space,verify_pins,exclusive_json
from runner.config_validation import load_and_validate

def require_approved_runtime(lock):
    if not lock.get('formal_runs_authorized') or not lock.get('native_integration_validated'):
        raise ControlError('FORMAL_EXECUTION_NOT_AUTHORIZED_AND_NATIVE_INTEGRATION_UNVERIFIED')
    raise ControlError('NATIVE_DISPATCH_NOT_RELEASED: never substitute synthetic execution')

def plan(experiment):
    lock=json.loads((ROOT/'configs/identity_lock.json').read_text());c=load_and_validate(ROOT/'configs'/f'{experiment}.yaml',lock)
    return {'experiment':experiment,'config':c,'lock':lock,'plan_valid':True,'formal_execution_ready':False,
        'restore_order':['source_and_pin_check','common_C0_validate','full_state_restore','RNG_restore_last','schedule_event_control'],
        'blockers':['REAL_C0_NOT_CAPTURED','NATIVE_RESUME_AND_EVENT_HOOKS_NOT_VALIDATED','CURRENT_AUTHORIZATION_CPU_SYNTHETIC_ONLY'],
        'run_order':['B1','B4','B2','B3'],'max_concurrent_models':1,'automatic_retry':False}

def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--experiment',required=True,choices=['B1','B2','B3','B4'])
    g=ap.add_mutually_exclusive_group();g.add_argument('--dry-run',action='store_true');g.add_argument('--validate-only',action='store_true')
    ap.add_argument('--output-root',type=pathlib.Path,default=ROOT/'artifacts/receipts')
    args=ap.parse_args(argv);p=plan(args.experiment)
    if args.dry_run:print(json.dumps({k:v for k,v in p.items() if k!='lock'},indent=2));return 0
    attempt='control-'+uuid.uuid4().hex;args.output_root.mkdir(parents=True,exist_ok=True)
    receipt={'attempt_id':attempt,'experiment':args.experiment,'formal_run_started':False,'cuda_initialized_by_runner':False}
    try:
        lock=p['lock']
        if args.validate_only:
            verify_pins(lock['remote_pins']);verify_pins(lock['execution_source_pins']);require_space(args.output_root,3*1024**3)
            c0=ROOT/lock['c0_ref']
            if not c0.is_dir():raise ControlError('REAL_C0_NOT_CAPTURED')
            from checkpoint.checkpoint_adapter import validate_checkpoint
            from schedule.replay import validate_schedule
            v=validate_checkpoint(c0)
            if v['artifact_kind']!='NATIVE_C0' or v['state_sha256']!=lock['c0_state_sha256']:raise ControlError('Synthetic/incorrect C0 cannot admit real run')
            if p['config']['schedule_mode']=='replay':validate_schedule(ROOT/p['config']['schedule_ref'],{'c0_sha256':v['state_sha256']})
            require_approved_runtime(lock)
        else:require_approved_runtime(lock)
    except Exception as e:
        receipt.update(status='BLOCKED',error=type(e).__name__,reason=str(e));exclusive_json(args.output_root/(attempt+'.json'),receipt)
        print(json.dumps(receipt));return 2
    return 2
if __name__=='__main__':raise SystemExit(main())
