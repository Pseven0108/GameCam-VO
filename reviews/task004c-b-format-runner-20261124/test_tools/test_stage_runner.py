"""Stage runner CPU mocks. No VIPER, model, CUDA, or native C0 execution."""
import ast,copy,hashlib,json,os,pathlib,sys,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch

import torch
from control_common import ControlError,digest
from native_control.stages import ORDER,mode_spec,schedule_scope,stage_limit
from native_control.runtime import NativeJournal,NativeControl,PrefixComplete,read_schedule
from native_control.dataset import NativeViperRGB
from src.utils.datasets import RGB_NoPose

OUT=pathlib.Path(sys.argv[1]);OUT.mkdir(parents=True,exist_ok=True)
ROOT=pathlib.Path(os.environ['GAMECAM_NATIVE_WORKSPACE'])

class StageTests(unittest.TestCase):
    def header(self,stage='short80'):
        return {'c0_sha256':'a'*64,'init_D':0,'W':1,'U':1,'max_rgb':stage_limit(stage),'stage':stage,'schedule':'S1','producer_D':1,'consumer_D':1}
    def test_all_mode_bounds(self):
        for mode in ORDER:
            s=mode_spec(mode)
            self.assertEqual(s['max_rgb'],stage_limit(s['stage']))
            with self.assertRaises(ControlError):mode_spec(mode,s['max_rgb']+1)
    def test_unknown_stage_mode(self):
        for x in ('formal488','anything',None):
            with self.assertRaises(ControlError):stage_limit(x)
            with self.assertRaises(ControlError):mode_spec(x)
    def test_formal_matrix(self):
        self.assertEqual([(mode_spec(x)['D'],mode_spec(x)['schedule'],mode_spec(x)['replay']) for x in ('B1','B2','B4','B3')],[(1,'S1',False),(0,'S1',True),(0,'S0',False),(1,'S0',True)])
    def test_header_rejects_scope_expansion(self):
        for key,value in [('W',0),('U',0),('init_D',1),('max_rgb',487),('stage','capture')]:
            h=self.header();h[key]=value
            with self.assertRaises(ControlError):schedule_scope(h)
    def journal(self,p,stage,replay=None):return NativeJournal(p,self.header(stage),mode='replay' if replay else 'record',source=replay)
    def fill(self,j,limit):
        context={'slot_rgb_tokens':['kf:001'],'graphs':[]}
        for rgb in range(19,limit+1):
            j.point('frame.begin',rgb,context,{'index':rgb-1})
            j.point('native.ba.begin',rgb,context,{'D_is_not_in_discrete_schedule':True},select=True)
            j.point('native.ba.end',rgb,context,{'call':rgb})
            j.point('frame.end',rgb,context,{'next_input_index':rgb})
    def test_short_full_event_roundtrip(self):
        p=OUT/'short_source.jsonl';j=self.journal(p,'short80');self.fill(j,80);j.seal()
        r=self.journal(OUT/'short_replay.jsonl','short80',p);self.fill(r,80);r.seal()
        self.assertEqual(read_schedule(p)['events'],read_schedule(OUT/'short_replay.jsonl')['events'])
    def test_formal_post_tracking_native_events(self):
        p=OUT/'formal_source.jsonl';j=self.journal(p,'formal487');self.fill(j,487)
        for kind in ('final.begin','final.end','filler.batch.begin','filler.batch.result','filler.batch.end','export'):
            j.point(kind,487,{}, {'event':kind})
        j.seal();self.assertEqual(read_schedule(p)['footer']['termination'],'FORMAL_RGB487_NATIVE_COMPLETE')
        r=self.journal(OUT/'formal_replay.jsonl','formal487',p);self.fill(r,487)
        for kind in ('final.begin','final.end','filler.batch.begin','filler.batch.result','filler.batch.end','export'):
            r.point(kind,487,{}, {'event':kind})
        r.seal()
    def test_short_cannot_read_formal(self):
        p=OUT/'formal_scope_source.jsonl';j=self.journal(p,'formal487');self.fill(j,487);j.seal()
        with self.assertRaises(ControlError):self.journal(OUT/'forbidden_short.jsonl','short80',p)
    def test_incomplete_schedule_cannot_seal(self):
        j=self.journal(OUT/'incomplete.jsonl','short80')
        with self.assertRaises(ControlError):j.seal()
        j.abort()
    def test_unpaired_event_latches_stop(self):
        j=self.journal(OUT/'unpaired.jsonl','short80')
        with self.assertRaises(ControlError):j.point('native.ba.end',19,{}, {})
        self.assertTrue(j.failed)
        with self.assertRaises(ControlError):j.point('frame.begin',19,{}, {'index':18})
        j.abort()
    def test_replay_rejects_changed_graph_context(self):
        p=OUT/'context_source.jsonl';j=self.journal(p,'short80');self.fill(j,80);j.seal()
        r=self.journal(OUT/'context_bad.jsonl','short80',p)
        with self.assertRaises(ControlError):r.point('frame.begin',19,{'slot_rgb_tokens':['WRONG'],'graphs':[]},{'index':18})
        r.abort()
    def controller(self,stage):
        p=OUT/('ctrl_'+stage);p.mkdir()
        return NativeControl(0,p,stage=stage)
    def test_actual_restore19_boundary(self):
        c=self.controller('restore19');c.frame_begin(18,18)
        with self.assertRaises(PrefixComplete):c.frame_end(None,None,{'next_input_index':19})
        self.assertEqual(c.rgb,19);c.trace.close()
    def test_formal_frame487_does_not_skip_termination(self):
        c=self.controller('formal487');c.frame_begin(486,486);c.frame_end(None,None,{'next_input_index':487})
        self.assertEqual(c.rgb,487)
        with self.assertRaises(ControlError):c.frame_begin(487,487)
        c.trace.close()
    def test_short_frame81_rejected(self):
        c=self.controller('short80')
        with self.assertRaises(ControlError):c.frame_begin(80,80)
        c.trace.close()
    def dataset(self,stage='capture'):
        d=object.__new__(NativeViperRGB);d.out=OUT;d.seen=18;d.stage=stage;d.filler_active=False;d.filler_seen=0;d.filler_finished=False
        d.n_img=487;d.depth_paths=None;d.poses=None
        d.frames=[{'rgb_id':i+1} for i in range(487)];d.color_paths=[str(OUT/'synthetic.jpg')]*487
        return d
    def fake_get(self,obj,index):return index,torch.zeros(1,3,360,640),torch.zeros(360,640,dtype=torch.float32),None
    def test_rgb019_not_cursor_only(self):
        d=self.dataset();d.set_stage('restore19')
        with patch.object(RGB_NoPose,'__getitem__',lambda obj,index:self.fake_get(obj,index)):
            ts,image,depth,pose=d[18]
            self.assertEqual(ts,18);self.assertEqual(tuple(image.shape),(1,3,360,640));self.assertEqual(d.seen,19)
            with self.assertRaises(ControlError):d[19]
    def test_filler_must_wait_for_tracking(self):
        d=self.dataset('formal487')
        with self.assertRaises(ControlError):d.task004_begin_filler()
    def test_filler_has_independent_ordered_cursor(self):
        d=self.dataset('formal487');d.seen=487;d.task004_begin_filler()
        with patch.object(RGB_NoPose,'__getitem__',lambda obj,index:self.fake_get(obj,index)):
            for i in range(487):self.assertEqual(d[i][0],i)
            self.assertEqual(d.seen,487);self.assertEqual(d.filler_seen,487)
            with self.assertRaises(IndexError):d[487]
        self.assertTrue(d.filler_finished)
        with self.assertRaises(ControlError):d.task004_begin_filler()
    def test_out_of_order_filler_rejected(self):
        d=self.dataset('formal487');d.seen=487;d.task004_begin_filler()
        with self.assertRaises(ControlError):d[1]
    def test_stage_transition_cannot_rewind(self):
        d=self.dataset();d.seen=19
        with self.assertRaises(ControlError):d.set_stage('formal487')
    def test_no_ba_formula_source_changes(self):
        import subprocess
        names=subprocess.check_output(['git','-C',str(ROOT/'source_candidate'),'diff','--name-only','0184690a51877223de32c78ada65002afa91103d'],text=True).splitlines()
        forbidden={'src/depth_video.py','src/lib/droid.cpp','src/lib/droid_kernels.cu','src/backend.py','src/frontend.py','src/factor_graph.py'}
        self.assertFalse(forbidden.intersection(names))
    def test_real_execution_is_not_claimed(self):
        self.assertFalse(torch.cuda.is_initialized())
        self.assertNotIn('CUDA_VISIBLE_DEVICES=0',os.environ.get('CUDA_VISIBLE_DEVICES',''))

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(StageTests))
    doc={'scope':'CPU_MOCK_STAGE_RUNNER_NOT_REAL_RGB_OR_GPU','total':result.testsRun,'passed':result.testsRun-len(result.errors)-len(result.failures),'failures':len(result.failures),'errors':len(result.errors),'cuda_initialized':torch.cuda.is_initialized(),'real_RGB019':False,'real_Short80':False,'real_Formal487':False}
    (OUT/'STAGE_CPU_REPORT.json').write_text(json.dumps(doc,indent=2));print(json.dumps(doc));sys.exit(0 if result.wasSuccessful() else 1)
