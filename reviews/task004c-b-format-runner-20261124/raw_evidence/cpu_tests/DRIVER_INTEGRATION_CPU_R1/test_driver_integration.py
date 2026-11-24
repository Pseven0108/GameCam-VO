"""Execute the actual restore driver with CPU-only boundary doubles, not a model."""
import ast,json,os,pathlib,sys,tempfile,types,unittest
from types import SimpleNamespace
from unittest.mock import patch
import torch
from control_common import ControlError,digest,file_sha
from native_control.runtime import NativeControl,NativeJournal,PrefixComplete,set_active,active,read_schedule
from native_control.stages import mode_spec

OUT=pathlib.Path(sys.argv[1]);OUT.mkdir(parents=True,exist_ok=True)
ROOT=pathlib.Path(os.environ['GAMECAM_NATIVE_WORKSPACE'])
source=(ROOT/'source_candidate/native_control/native_driver.py').read_text()
function=next(x for x in ast.parse(source).body if isinstance(x,ast.FunctionDef) and x.name=='restore_and_continue')

class Sink:
    def __init__(self,*a):self.progress_counter=SimpleNamespace(value=0)
    def pbar_ready(self):pass
    def print(self,*a,**kw):pass
    def terminate(self):pass
    def flush(self):pass
    def close(self):pass
class Writer(Sink):pass
class Barrier:
    def __init__(self,*a):self.request=SimpleNamespace(clear=lambda:None)
class Process:
    exitcode=0
    def __init__(self,*a,**kw):pass
    def start(self):pass
    def join(self,**kw):pass
    def is_alive(self):return False
class Context:
    def Value(self,*a):return SimpleNamespace(value=0)
    def Pipe(self):return object(),object()
    def Event(self):return SimpleNamespace(set=lambda:None)
    def Process(self,*a,**kw):return Process()
class Stream:
    def __init__(self):self.seen=18;self.filler_seen=0;self.filler_finished=False;self.out=None;self.inputs=[]
    def set_stage(self,s):self.stage=s
class Tracker:
    def __init__(self,p):
        self.video=SimpleNamespace(counter=SimpleNamespace(value=1),timestamp=torch.tensor([0.]),poses=torch.tensor([[0.,0.,0.,0.,0.,0.,1.]]))
        self.frontend=SimpleNamespace(graph=object());self.cfg={'scene':'synthetic','data':{'output':str(p)}}
        self.net=object();self.device='cpu';self.output=str(p/'synthetic')
    def run(self,s):
        c=active()
        for i in range(18,c.max_rgb):
            c.frame_begin(i,i);s.inputs.append(i+1);s.seen+=1
            c.frame_end(self,s,{'next_input_index':i+1})
class NativeShell:
    def backend(self):
        for stage in (1,2):
            active().final_phase('begin',stage=stage,steps=7 if stage==1 else 12,metric_depth_reg=False)
            active().final_phase('end',stage=stage)
    def terminate(self):
        self.backend();self.stream.filler_seen=487;self.stream.filler_finished=True
        p=pathlib.Path(self.save_dir)/'traj';p.mkdir()
        (p/'est_poses_full.txt').write_text(('0 0 0 0 0 0 0 1\n')*487)
        active().export(list(range(1,488)),['MOCK']*487)
        self.final_clean=True

class DriverTests(unittest.TestCase):
    def invoke(self,mode):
        root=OUT/mode;root.mkdir();(root/'attempts/capture').mkdir(parents=True)
        out=root/'attempts'/mode;out.mkdir(exist_ok=True)
        (root/'attempts/capture/C0_RECEIPT.json').write_text(json.dumps({'state_sha256':'c'*64}))
        tracker=Tracker(out);stream=Stream();observer=SimpleNamespace(path=None)
        timer=object();counter=tracker.video.counter
        discrete={'nodes':['kf:001'],'rgb':18,'initialized':True,'init_counts':{},'ba_calls':24,
                  'next_graph':0,'next_edge':0,'edge_state':{},'graph_ids':{}}
        bundle={'tracker':tracker,'stream':stream,'filler':SimpleNamespace(cfg=tracker.cfg),'cursor':{'next_input_index':18},
                'control':discrete,'observer':observer,'timer':timer,'next_input':{'rgb_id':19,'input_index':18}}
        manifest={'state_sha256':'c'*64,'provenance':{'candidate_source_commit':'COMMIT'}}
        def restore(*a,**kw):return bundle,manifest,{'source_pid':0,'new_process_pid':os.getpid()}
        def rebind(b,o):return {'only_diagnostic_paths':True}
        fake_observer=types.ModuleType('task003_observer');fake_timers=types.ModuleType('src.utils.sys_timer')
        env={'GAMECAM_NATIVE_SOURCE_COMMIT':'COMMIT','TORCH_HOME':str(root/'hub')}
        for repo in ('yvanyin_metric3d_main','ywyue_FiT3D_main'):
            p=root/'hub'/repo;p.mkdir(parents=True);(p/'hubconf.py').touch()
        namespace={'torch':torch,'cv2':SimpleNamespace(setNumThreads=lambda x:None),'os':os,'pathlib':pathlib,'json':json,
            'mp':SimpleNamespace(get_context=lambda x:Context()),'WriterBarrier':Barrier,'RestoreIOPrinter':Sink,'SummaryWriter':Writer,
            'read_manifest':lambda *a:manifest,'restore_c0':restore,'ControlError':ControlError,'mode_spec':mode_spec,
            'NativeJournal':NativeJournal,'NativeControl':NativeControl,'set_active':set_active,'rebind_output':rebind,
            'digest':digest,'file_sha':file_sha,'native_recording_viewer':lambda *a,**kw:None,'SLAM':NativeShell,'PrefixComplete':PrefixComplete}
        with patch.dict(os.environ,env),patch.dict(sys.modules,{'task003_observer':fake_observer,'src.utils.sys_timer':fake_timers}),patch('torch.cuda.set_device'),patch('torch.empty',return_value=torch.tensor([])):
            exec(compile(ast.Module(body=[function],type_ignores=[]),'<ACTUAL_DRIVER_AST>','exec'),namespace)
            try:namespace['restore_and_continue'](root,out,mode,{'input_manifest_sha256':'I'})
            finally:
                c=active()
                if getattr(c,'enabled',False) and not c.trace.closed:c.trace.close()
                set_active(None)
        return json.loads((out/'SUCCESS.json').read_text()),stream,out
    def test_driver_processes_actual_mock_input19(self):
        r,s,out=self.invoke('restore_check')
        self.assertEqual(s.inputs,[19]);self.assertTrue(r['actual_RGB019_consumed']);self.assertEqual(r['next_unread_rgb'],20)
    def test_driver_records_all_short80_frames(self):
        r,s,out=self.invoke('record_S1')
        self.assertEqual(s.inputs,list(range(19,81)));self.assertEqual(read_schedule(out/'schedule.jsonl')['events'][-1]['rgb'],80)
    def test_driver_reaches_native_final_ba_and_filler(self):
        r,s,out=self.invoke('B1')
        self.assertEqual(s.inputs,list(range(19,488)));self.assertEqual(r['pose_rows'],487);self.assertTrue(s.filler_finished)
        events=read_schedule(out/'schedule.jsonl')['events']
        self.assertEqual(sum(e['kind']=='final.begin' for e in events),2)
        self.assertTrue((out/'FRONTEND_KEYFRAMES.npz').is_file());self.assertTrue((out/'FINAL_BA_KEYFRAMES.npz').is_file())

if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DriverTests))
    doc={'total':r.testsRun,'passed':r.testsRun-len(r.failures)-len(r.errors),'failures':len(r.failures),'errors':len(r.errors),
        'scope':'ACTUAL_DRIVER_CPU_MOCK_NOT_REAL_RGB_GPU','cuda_initialized':torch.cuda.is_initialized(),'actual_VIPER_or_models':False}
    (OUT/'DRIVER_INTEGRATION_CPU_REPORT.json').write_text(json.dumps(doc,indent=2));print(json.dumps(doc));sys.exit(0 if r.wasSuccessful() else 1)
