"""Stage-qualified CLI. No framework import until sealed admission succeeds."""
import argparse,hashlib,json,os,pathlib,subprocess,sys,time
ROOT=pathlib.Path(os.environ.get('GAMECAM_NATIVE_WORKSPACE',pathlib.Path(__file__).absolute().parents[1]));sys.path.insert(0,str(ROOT))
from native_control.admission import preflight,sha
from native_control.stages import ORDER,MODES,mode_spec
from control_common import ControlError


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=MODES,required=True)
    p.add_argument('--max-rgb',type=int)
    p.add_argument('--cpu-report',type=pathlib.Path,required=True)
    p.add_argument('--execute',action='store_true');p.add_argument('--model-child',action='store_true')
    a=p.parse_args(argv);spec=mode_spec(a.mode,a.max_rgb)
    if not a.execute:
        print(json.dumps({**spec,'plan_only':True,'models_imported':False,'automatic_retries':0}));return 0
    token=json.loads((ROOT/'evidence/CPU_STAGE_RELEASE.json').read_text())
    if sha(a.cpu_report)!=token['cpu_report_sha256']:raise SystemExit('CPU_REPORT_RELEASE_SHA_MISMATCH')
    for name,expected in token['candidate_pins'].items():
        if sha(ROOT/name)!=expected:raise SystemExit('CANDIDATE_CODE_SHA_CHANGED: '+name)
    candidate=ROOT/'source_candidate'
    def git(*args):return subprocess.check_output(['git','-C',str(candidate),*args],text=True).strip()
    if git('rev-parse','HEAD')!=token['candidate_commit'] or git('status','--porcelain','--untracked-files=all'):
        raise SystemExit('FINAL_RUNNER_COMMIT_OR_WORKTREE_MISMATCH')
    if a.model_child:
        intent=ROOT/'attempts'/a.mode/'LAUNCH_INTENT.json'
        receipt=json.loads(intent.read_text())
        if (receipt['spec']!=spec or receipt['source_commit']!=token['candidate_commit'] or
            os.environ.get('GAMECAM_NATIVE_INTERNAL_CHILD')!=receipt['child_token']):
            raise SystemExit('STAGE_CHILD_NOT_ADMITTED')
        sys.path.insert(0,str(candidate))
        # Inherited policy guard remains active; the stage grant is additional.
        from task004_controls import require_approved_runtime
        require_approved_runtime()
        from native_control.native_driver import capture,restore_and_continue
        lock=json.loads((ROOT/'configs/identity_lock.json').read_text());out=intent.parent
        if a.mode=='capture':
            capture(ROOT,out,token['input_manifest'],token['r2_config'],lock)
        else:restore_and_continue(ROOT,out,a.mode,lock)
        return 0
    index=ORDER.index(a.mode)
    for previous in ORDER[:index]:
        q=ROOT/'attempts'/previous
        if not (q/'SUCCESS.json').is_file() or not (q/'PROCESS_RECEIPT.json').is_file():
            raise SystemExit('PREVIOUS_STAGE_NOT_COMPLETE: '+previous)
        r=json.loads((q/'PROCESS_RECEIPT.json').read_text())
        if r['exit_code']!=0:raise SystemExit('PREVIOUS_STAGE_FAILED: '+previous)
    if a.mode!='capture':
        from native_control.admission import continuation_preflight
        admission=continuation_preflight(ROOT,token)
    else:
        lock=json.loads((ROOT/'configs/identity_lock.json').read_text())
        admission=preflight(ROOT,lock,cpu_report=a.cpu_report,cpu_storage_backend='owned_file_mmap',storage_validation=ROOT/'evidence/FILE_BACKED_CPU_VALIDATION.json')
    with (ROOT/'artifacts'/('GPU_ADMISSION_'+a.mode+'.json')).open('x') as f:json.dump(admission,f,indent=2)
    if not admission['admitted']:
        print(json.dumps({'status':'BLOCKED_BEFORE_MODEL_IMPORT','issues':admission['issues'],'mode':a.mode,'runs_started':0}));return 2
    out=ROOT/'attempts'/a.mode;out.mkdir(parents=True,exist_ok=False)
    child_token=hashlib.sha256(os.urandom(32)).hexdigest()
    intent={'mode':a.mode,'spec':spec,'source_commit':token['candidate_commit'],'child_token':child_token,
            'created':time.time(),'automatic_retry':False}
    with (out/'LAUNCH_INTENT.json').open('x') as f:json.dump(intent,f,indent=2)
    data=token['asset_root']
    env=dict(os.environ,PYTHONPATH=str(ROOT)+':'+str(candidate)+':'+str(ROOT/'operational'),PYTHONHASHSEED='43',
        PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
        CUDA_VISIBLE_DEVICES='0',GAMECAM_NATIVE_WORKSPACE=str(ROOT),GAMECAM_FILE_BACKED_CPU_ROOT=str(out/'shared_cpu'),
        TORCH_HOME=data+'/torch_hub',HF_HOME=data+'/huggingface',HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',
        MPLBACKEND='Agg',RERUN_NO_ANALYTICS='1',GAMECAM_NATIVE_CONTROL_BOUNDED='1',
        GAMECAM_NATIVE_INTERNAL_CHILD=child_token,GAMECAM_NATIVE_ATTEMPT=str(out),
        GAMECAM_NATIVE_SOURCE_COMMIT=token['candidate_commit'],GAMECAM_NATIVE_SOURCE_TREE=git('rev-parse','HEAD^{tree}'),
        GAMECAM_NATIVE_LOCK=str(ROOT/'configs/identity_lock.json'),GAMECAM_TASK003_OBSERVER_JSONL=str(out/'observer.jsonl'),
        GAMECAM_NATIVE_APPROVED_MODE=a.mode,
        GAMECAM_TASK004_POLICY=token['policy_path'],GAMECAM_TASK004_POLICY_SHA256=token['policy_sha256'])
    cmd=[sys.executable,'-B',str(ROOT/'operational/stage_entry.py'),'--mode',a.mode,'--max-rgb',str(spec['max_rgb']),
         '--cpu-report',str(a.cpu_report),'--execute','--model-child']
    start=time.time()
    with (out/'process.stdout.txt').open('xb') as stdout,(out/'process.stderr.txt').open('xb') as stderr:
        q=subprocess.run(cmd,env=env,cwd=candidate,stdout=stdout,stderr=stderr,timeout=2400)
    receipt={'mode':a.mode,'spec':spec,'exit_code':q.returncode,'success_receipt_exists':(out/'SUCCESS.json').is_file(),
             'run_consumed':True,'retry_allowed':False,'runtime_seconds':time.time()-start,
             'stdout_sha256':sha(out/'process.stdout.txt'),'stderr_sha256':sha(out/'process.stderr.txt')}
    (out/'PROCESS_RECEIPT.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))
    return 0 if q.returncode==0 and receipt['success_receipt_exists'] else 1

if __name__=='__main__':raise SystemExit(main())
