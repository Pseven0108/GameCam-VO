"""Authorization-gated real child entry. Audit calls only verify rejection, before any model import."""
import argparse,json,os,pathlib,sys,time
from launch_contract import AUDIT,ROOT,REFERENCE,FUTURE_ROOT,PREPARED_SHA,PREFLIGHT,load,sha,require_authorization

def main():
    p=argparse.ArgumentParser();p.add_argument('--authorization');p.add_argument('--session-dir');p.add_argument('--session');a=p.parse_args()
    try:
        require_authorization(AUDIT/'10_launch_contract_candidate.json',a.authorization)
    except BaseException as exc:
        print(json.dumps({'status':'MODEL_EXECUTION_NOT_AUTHORIZED','reason':str(exc),'torch_imported':'torch' in sys.modules,'model_attempts':0,'model_constructed':False,'checkpoint_deserialized':False}),flush=True);return 3
    if not a.session_dir or not a.session:raise RuntimeError('Missing supervised session')
    ledger=load(FUTURE_ROOT/'model_attempt.json')
    if ledger['session']!=a.session or ledger['attempt_number']!=1 or ledger['contract_sha256']!=sha(AUDIT/'10_launch_contract_candidate.json'):raise RuntimeError('Single-attempt ledger mismatch')
    if int(os.environ.get('GAMECAM_SUPERVISOR_PID','-1'))!=os.getppid():raise RuntimeError('Invalid owning supervisor')
    from runtime_dependency_pins import RuntimePins
    from model_io_boundary import ModelIOBoundary
    spec=load(REFERENCE/'config/dependency_pins.json');case=load(REFERENCE/'config/cases.json')[0]
    os.environ.update(spec['environment']);os.environ.update(PYTHONDONTWRITEBYTECODE='1',MPLBACKEND='Agg',QT_QPA_PLATFORM='offscreen',OMP_NUM_THREADS='2',GAMECAM_XFORMERS_DISABLE_FA3='1',GAMECAM_RUN_SESSION_DIR=a.session_dir)
    cfg=load(PREFLIGHT/'GPU_09_120frame_effective_config.json');out=pathlib.Path(cfg['data']['output']);out.mkdir(parents=True,exist_ok=False)
    boundary=ModelIOBoundary(spec,case,out,a.session_dir);boundary.install()
    class PinnedRuntime(RuntimePins):
        def effective_config(self,output):
            self.read_original_config()
            if sha(PREFLIGHT/'GPU_09_120frame_effective_config.json')!=PREPARED_SHA:raise RuntimeError('Prepared configuration SHA drift')
            c=load(PREFLIGHT/'GPU_09_120frame_effective_config.json')
            if c['data']['output']!=str(output):raise RuntimeError('Output differs from frozen 120-frame configuration')
            return c
    result={'version':'K6-A-GPU-R2-native-linux-adapter','attempt_id':a.session,'method':'droidw','case_id':'V56_01_middle','status':'RUNNING','started_unix':time.time(),'frames_submitted':0,'frames_completed':0,'frames':[],'initialization':None,'native_snapshots':[],'mapping_events':[],'checkpoint_loads':[],'error':None,'gt_input':False,'trajectory_filler_executed':False,'final_BA_executed':False,'final_refinement_executed':False,'dependency_pin_events':[]}
    from linux_safety import atomic_json
    def save():atomic_json(out/'result.json',result)
    pins=PinnedRuntime(REFERENCE,event_sink=lambda event:result['dependency_pin_events'].append(event));pins.static_check();pins.install_before_import()
    import torch,cv2,numpy as np
    pins.assert_hooks(require_torch=True)
    from native_adapter import _native_runtime
    from types import SimpleNamespace
    args=SimpleNamespace(method='droidw',case='V56_01_middle',monitor_session_id=a.session)
    code=_native_runtime(FUTURE_ROOT,args,case,out,result,save,torch,cv2,np,pins)
    result['IO_boundary_denied_events']=boundary.events;save();return code
if __name__=='__main__':raise SystemExit(main())