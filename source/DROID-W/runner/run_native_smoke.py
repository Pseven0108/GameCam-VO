"""Bounded native validation CLI; the formal experiment runner stays locked."""
import argparse,hashlib,json,os,pathlib,subprocess,sys,time
ROOT=pathlib.Path(os.environ.get('GAMECAM_NATIVE_WORKSPACE',pathlib.Path(__file__).absolute().parents[1]));sys.path.insert(0,str(ROOT))
from native_control.admission import MODES,preflight,sha,validate_mode

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=MODES,required=True)
    p.add_argument('--max-rgb',type=int,default=80);p.add_argument('--cpu-report',type=pathlib.Path,required=True)
    p.add_argument('--execute',action='store_true');p.add_argument('--model-child',action='store_true')
    a=p.parse_args(argv);validate_mode(a.mode,a.max_rgb)
    lock=json.loads((ROOT/'configs/identity_lock.json').read_text())
    if not a.execute:
        print(json.dumps({'mode':a.mode,'max_rgb':80,'models_imported':False,'formal_runs_authorized':False,'retries':0,
                         'plan_only':True,'sequence':'val_007','init_D':0,'W':1,'U':1}));return 0
    release=ROOT/'evidence/CPU_NATIVE_RELEASE.json'
    if not release.is_file():raise SystemExit('CPU_NATIVE_RELEASE_NOT_PUBLISHED')
    token=json.loads(release.read_text())
    if sha(a.cpu_report)!=token['cpu_report_sha256']:raise SystemExit('CPU_REPORT_RELEASE_SHA_MISMATCH')
    for name,expected in token['candidate_pins'].items():
        if sha(ROOT/name)!=expected:raise SystemExit('CANDIDATE_CODE_SHA_CHANGED: '+name)
    if a.model_child:
        intent=ROOT/'attempts'/a.mode/'LAUNCH_INTENT.json'
        receipt=json.loads(intent.read_text())
        if receipt['mode']!=a.mode or receipt['max_rgb']!=80 or receipt['formal_experiment'] or os.environ.get('GAMECAM_NATIVE_INTERNAL_CHILD')!=receipt['child_token']:
            raise SystemExit('BOUNDED_CHILD_NOT_ADMITTED')
        # Model/framework imports occur only beyond this boundary.
        sys.path.insert(0,str(ROOT/'source_candidate'))
        from native_control.native_driver import capture,restore_and_continue
        out=intent.parent
        if a.mode=='capture':
            capture(ROOT,out,'/root/rivermind-data/DROID_W_TASK003_VAL007_OBSERVATION_R1/inputs/val_007_full_00001-00487/INPUT.json',
                    '/root/rivermind-data/DROID_W_TASK004B_CONFIRMATORY_20261123T124144277Z/release/candidates/r2_sealed_config.yaml',lock)
        else:restore_and_continue(ROOT,out,a.mode,lock)
        return 0
    admission=preflight(ROOT,lock,cpu_report=a.cpu_report,cpu_storage_backend='owned_file_mmap',storage_validation=ROOT/'evidence/FILE_BACKED_CPU_VALIDATION.json')
    target=ROOT/'artifacts'/('GPU_ADMISSION_'+a.mode+'.json')
    with target.open('x') as f:json.dump(admission,f,indent=2)
    if not admission['admitted']:
        print(json.dumps({'status':'BLOCKED_BEFORE_MODEL_IMPORT','issues':admission['issues'],'mode':a.mode,'runs_started':0}));return 2
    # Claim after a successful preflight, but before framework/model import.
    out=ROOT/'attempts'/a.mode;out.mkdir(parents=True,exist_ok=False)
    token_value=hashlib.sha256(os.urandom(32)).hexdigest()
    intent={'mode':a.mode,'max_rgb':80,'formal_experiment':False,'child_token':token_value,'created':time.time(),'automatic_retry':False}
    with (out/'LAUNCH_INTENT.json').open('x') as f:json.dump(intent,f,indent=2)
    data='/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data'
    env=dict(os.environ,PYTHONPATH=str(ROOT)+':'+str(ROOT/'source_candidate'),PYTHONHASHSEED='43',
         PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
         CUDA_VISIBLE_DEVICES='0',GAMECAM_NATIVE_WORKSPACE=str(ROOT),GAMECAM_FILE_BACKED_CPU_ROOT=str(out/'shared_cpu'),TORCH_HOME=data+'/torch_hub',HF_HOME=data+'/huggingface',HF_HUB_OFFLINE='1',
         HF_HUB_DISABLE_TELEMETRY='1',MPLBACKEND='Agg',RERUN_NO_ANALYTICS='1',GAMECAM_NATIVE_CONTROL_BOUNDED='1',
         GAMECAM_NATIVE_INTERNAL_CHILD=token_value,GAMECAM_NATIVE_ATTEMPT=str(out),GAMECAM_NATIVE_LOCK=str(ROOT/'configs/identity_lock.json'),
         GAMECAM_TASK003_OBSERVER_JSONL=str(out/'observer.jsonl'))
    cmd=[sys.executable,'-B',str(pathlib.Path(__file__).resolve()),'--mode',a.mode,'--max-rgb','80','--cpu-report',str(a.cpu_report),'--execute','--model-child']
    with (out/'process.stdout.txt').open('xb') as stdout,(out/'process.stderr.txt').open('xb') as stderr:
        q=subprocess.run(cmd,env=env,cwd=ROOT/'source_candidate',stdout=stdout,stderr=stderr,timeout=1800)
    result={'mode':a.mode,'exit_code':q.returncode,'success_receipt_exists':(out/'SUCCESS.json').is_file(),'run_consumed':True,'retry_allowed':False}
    (out/'PROCESS_RECEIPT.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
    return 0 if q.returncode==0 and result['success_receipt_exists'] else 1

if __name__=='__main__':raise SystemExit(main())
