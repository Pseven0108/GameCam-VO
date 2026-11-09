"""Future GPU child; fresh authorization and claimed ledger are checked before model imports."""
import argparse,csv,json,os,pathlib,sys,time
from diagnostic_authorization import DiagnosticContext
from runtime_dependency_pins import RuntimePins,digest_file,require

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--candidate-sha',required=True);p.add_argument('--authorization');p.add_argument('--session-dir');p.add_argument('--session');a=p.parse_args(argv)
    ctx=DiagnosticContext(a.candidate,a.candidate_sha,a.authorization)
    try:c=ctx.validate_child(a.session_dir,a.session)
    except BaseException as e:
        print(json.dumps({'status':'CHILD_PREIMPORT_REJECTED','reason':str(e),'torch_imported':'torch' in sys.modules,'new_attempts':0}),flush=True);return 3
    root=pathlib.Path(c['source_root']);phase=root/c['runtime_phase_relative'];out=pathlib.Path(c['planned_model_output'])
    require(not out.exists(),'MODEL_OUTPUT_ALREADY_EXISTS','BLOCKED_BY_AUTHORIZATION_GUARD')
    os.environ.update(c['pinned_environment']);os.environ['GAMECAM_RUN_SESSION_DIR']=a.session_dir
    class PreparedPins(RuntimePins):
        def effective_config(self,output):
            self.read_original_config();r=c['effective_config_record'];require(digest_file(r['path'])==r['sha256'],'EFFECTIVE_CONFIG_SHA_DRIFT','BLOCKED_BY_CONFIG_PIN')
            cfg=json.loads(pathlib.Path(r['path']).read_text());expected=json.loads(json.dumps(self._checked_original));expected['max_frames']=120;expected['data']['output']=str(output)
            require(cfg==expected and str(output)==c['planned_model_output'],'EFFECTIVE_CONFIG_UNAPPROVED_CHANGE','BLOCKED_BY_CONFIG_PIN');return cfg
    pins=PreparedPins(phase);pins.static_check()
    case=json.loads((phase/'config/cases.json').read_text(encoding='utf-8-sig'))[0]
    reads=[str(phase/'config/dependency_pins.json'),c['effective_config_record']['path']]
    for r in pins.spec['files'].values():reads.append(str(phase/r['path']))
    for r in [pins.spec['config'],pins.spec['k4_live_contract']]+list(pins.weights.values()):reads.extend([r['path_linux'],r['real_linux']])
    reads.extend([pins.spec['hf']['ref_path_linux'],pins.spec['hf']['ref_real_linux']]);reads.extend(f['path_linux'] for f in case['frames'])
    from ipc_runtime import IPCPolicy,verify_runtime_contract
    verify_runtime_contract(c['ipc_contract_record'])
    policy=IPCPolicy(c['planned_ipc_root'],str(pathlib.Path(a.session_dir)/'tmp'),a.session,a.session_dir)
    policy.install_arena()
    # Native dataset construction globs the input directory; actual reads are limited to these 120 files.
    from model_io_boundary_v2 import ModelIOBoundary
    session_dir=pathlib.Path(a.session_dir).resolve()
    worker_files=[
        session_dir/'cuda_samples.jsonl',
        session_dir/'cuda.latest.json',
        session_dir/'frame_samples.jsonl',
        session_dir/'ipc_worker_events.jsonl',
        session_dir/'worker_terminal.json',
    ]
    worker_read_files=[
        session_dir/'work.permit.json',
        session_dir/'nvml.latest.json',
        session_dir/'supervisor_heartbeat.jsonl',
        session_dir/'supervisor_stop.json',
    ]
    boundary=ModelIOBoundary(
        reads,
        [str(root/r['path']) for r in c['source_records']]+[r['path'] for r in c.get('external_source_records',[])],
        [root,c['external_production_root']],
        [out],
        [c['runtime_environment_prefix']],
        ipc_policy=policy,
        worker_files=worker_files,
        worker_read_files=worker_read_files,
        worker_atomic_files=[session_dir/'cuda.latest.json', session_dir/'worker_terminal.json'],
        worker_root=session_dir,
    )
    boundary.install()
    out.mkdir(parents=True,exist_ok=False,mode=0o700)
    scratch=pathlib.Path(a.session_dir)/'tmp'
    require(os.environ.get('TMPDIR')==str(scratch),'TEMP_DIRECTORY_NOT_PINNED','BLOCKED_BY_AUTHORIZATION_GUARD')
    require(scratch.is_dir() and scratch.resolve()==scratch,'IPC_FALLBACK_NOT_PREPARED','BLOCKED_BY_AUTHORIZATION_GUARD')
    result={'version':'K6-A-R2-BOUNDED-DIAGNOSTIC','method':'droidw','case_id':'V56_01_middle','status':'RUNNING','started_unix':time.time(),'frames_submitted':0,'frames_completed':0,'frames':[],'initialization':None,'native_snapshots':[],'mapping_events':[],'checkpoint_loads':[],'error':None,'gt_input':False,'trajectory_filler_executed':False,'final_BA_executed':False,'final_refinement_executed':False,'dependency_pin_events':[]}
    from linux_safety import atomic_json
    def save():atomic_json(out/'result.json',result)
    from diagnostic_phases import PhaseRecorder
    diagnostic=PhaseRecorder(out,a.session_dir,a.session)
    diagnostic.emit('PROCESS_STARTED',edge='point')
    def dependency_event(event):
        result['dependency_pin_events'].append(event);diagnostic.dependency_event(event)
    pins.event_sink=dependency_event
    pins.install_before_import()
    with diagnostic.span('TORCH_IMPORT'):
        import torch,cv2,numpy as np
    diagnostic.torch=torch
    pins.assert_hooks(require_torch=True)
    from native_adapter_v2 import _native_runtime
    from types import SimpleNamespace
    args=SimpleNamespace(method='droidw',case='V56_01_middle',monitor_session_id=a.session)
    def terminal_callback():
        from worker_terminal import publish_terminal
        result['io_boundary_denied_events']=boundary.events
        result['ipc_events']=list(policy.events)
        save()
        publish_terminal(a.session_dir,a.session,out/'result.json','droidw_diagnostic')
    return _native_runtime(root/'planned-v2-runtime-root',args,case,out,result,save,torch,cv2,np,pins,terminal_callback=terminal_callback,diagnostic=diagnostic)
if __name__=='__main__':raise SystemExit(main())
