"""CPU contracts for phase isolation and fixed-map scaling of native BA inputs."""
import pathlib,sys,tempfile,types,unittest
import torch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from scale_controller import install,MAIN

droid_backends=None

class Backend:
    def __init__(self):self.calls=[];self.filters=[]
    def ba(self,*args):
        self.calls.append(args)
        return torch.zeros(2,6),torch.zeros(4,20,24)
    def depth_filter(self,poses,disps,k,idx,thresh):
        self.filters.append((len(poses),len(disps),idx.clone()))
        return torch.full((len(idx),20,24),3.)

class Video:
    def __init__(self):
        self.device='cpu';self.counter=types.SimpleNamespace(value=4)
        self.timestamp=torch.arange(4,dtype=torch.float32)
        self.metric_depth_reg=True;self._local_input_timestamp=3;self._local_scale_stage=MAIN
    def ba(self,*args):return droid_backends.ba(*args)

class Tests(unittest.TestCase):
    def setUp(self):
        global droid_backends
        self.backend=Backend();droid_backends=self.backend
        self.video=Video();self.candidate=Backend();self.temp=tempfile.TemporaryDirectory()
        self.args=[None]*30
        for i in [0,1,2,3,4,5,6,11,12]:self.args[i]=torch.zeros(1)
        self.args[0]=torch.zeros(9,7);self.args[0][:,6]=1
        self.args[1]=torch.full((9,20,24),2.)
        self.args[2]=torch.tensor([48.,48.,40.,22.])
        self.args[3]=torch.ones(9,20,24)
        self.args[5]=torch.ones(4,2,20,24)
        self.args[6]=torch.ones(9,20,24)
        self.args[11]=torch.arange(4);self.args[12]=torch.arange(4)
        self.args[15]=2;self.args[20]=.01;self.args[23]=False
        self.coefficients={i:torch.full((20,24),.7) for i in range(4)}
    def tearDown(self):self.temp.cleanup()
    def setup_controller(self,scale=True,a5=False):
        install(self.video,self.candidate if a5 else None,scale_enabled=scale,a5_enabled=a5,
            coefficients=self.coefficients,log_path=pathlib.Path(self.temp.name)/'calls.jsonl')
    def test_missing_stage_stops(self):
        self.setup_controller();del self.video._local_scale_stage
        with self.assertRaises(RuntimeError):self.video.ba(*self.args)
        self.assertEqual(len(self.backend.calls),0)
    def test_incorrect_stage_stops(self):
        self.setup_controller();self.video._local_scale_stage='WRONG'
        with self.assertRaises(RuntimeError):self.video.ba(*self.args)
    def test_initialization_is_native(self):
        self.setup_controller(a5=True);self.video._local_scale_stage='INITIALIZATION'
        self.video.ba(*self.args)
        self.assertIs(self.backend.calls[0][3],self.args[3]);self.assertFalse(self.candidate.calls)
        self.assertFalse(self.backend.filters)
    def test_final_and_filler_are_native(self):
        self.setup_controller(a5=True)
        for stage in ['INITIALIZATION_SECOND_STAGE','FINAL_GLOBAL_BA','TRAJECTORY_FILLER','ONLINE_GLOBAL_BA']:
            self.video._local_scale_stage=stage;self.video.ba(*self.args)
        self.assertEqual(len(self.backend.calls),4);self.assertFalse(self.candidate.calls)
    def test_motion_only_is_native(self):
        self.setup_controller(a5=True);self.args[23]=True;self.video.ba(*self.args)
        self.assertFalse(self.candidate.calls);self.assertFalse(self.backend.filters)
    def test_active_frame_bound_and_no_pose_mutation(self):
        self.setup_controller();poses=self.args[0].clone();self.video.ba(*self.args)
        self.assertEqual(self.backend.filters[0][:2],(4,4))
        self.assertTrue(torch.equal(poses,self.args[0]))
    def test_scale_excludes_newest_and_preserves_raw_prior(self):
        self.setup_controller();self.video.ba(*self.args)
        corrected=self.backend.calls[0][3]
        self.assertTrue(torch.equal(corrected[:3],torch.full((3,20,24),2.)))
        self.assertTrue(torch.equal(corrected[3:],self.args[3][3:]))
        self.assertTrue(torch.equal(self.args[3],torch.ones_like(self.args[3])))
    def test_repeated_call_does_not_accumulate_scale(self):
        self.setup_controller();self.video.ba(*self.args);self.video.ba(*self.args)
        self.assertEqual(len(self.backend.filters),1)
        self.assertTrue(torch.equal(self.backend.calls[0][3],self.backend.calls[1][3]))
    def test_no_graph_support_is_identity_fallback(self):
        self.setup_controller();self.args[11]=torch.full((4,),3);self.video.ba(*self.args)
        self.assertTrue(torch.equal(self.backend.calls[0][3],self.args[3]))
    def test_a5_uses_independent_strength_without_changing_weights(self):
        self.setup_controller(scale=False,a5=True);self.video.ba(*self.args)
        call=self.candidate.calls[0]
        self.assertEqual(len(call),33);self.assertIs(call[3],self.args[3]);self.assertIs(call[5],self.args[5])
        self.assertTrue(torch.equal(call[30][:4],torch.full((4,20,24),.7)))
    def test_metric_prior_disabled_is_native(self):
        self.setup_controller(a5=True);self.video.metric_depth_reg=False;self.video.ba(*self.args)
        self.assertFalse(self.candidate.calls);self.assertFalse(self.backend.filters)
    def test_fractional_timestamp_stops(self):
        self.setup_controller();self.video.timestamp[0]=.2
        with self.assertRaises(RuntimeError):self.video.ba(*self.args)
    def test_missing_a5_cache_stops(self):
        self.setup_controller(a5=True);del self.coefficients[2]
        with self.assertRaises(KeyError):self.video.ba(*self.args)
    def test_out_of_range_coefficient_stops(self):
        self.setup_controller(a5=True);self.coefficients[0][0,0]=1.1
        with self.assertRaises(RuntimeError):self.video.ba(*self.args)
    def test_double_install_stops(self):
        self.setup_controller()
        with self.assertRaises(RuntimeError):self.setup_controller()

if __name__=='__main__':unittest.main(verbosity=2)
