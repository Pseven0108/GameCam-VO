import ast, copy, dataclasses, hashlib, io, json, multiprocessing, os, pathlib, random, subprocess, sys, tempfile, threading, time, types, unittest
from unittest.mock import patch
import numpy as np
import torch
from control_common import ControlError,digest,file_sha
from native_control.snapshot import save_state,load_state,read_manifest,state_inventory,ObjectEncoder
from native_control.cpu_fixtures import FixtureObject,NoConstructorFixture,fixture_bundle
from native_control.runtime import NativeControl,NativeJournal,PrefixComplete,read_schedule,set_active,active
from native_control.barrier import WriterBarrier
from native_control.install import install_factor_graph,install_depth_video,selected_flags
from native_control.cpu_native_bodies import load_class,FakeVideo,fake_update
from native_control.admission import validate_mode
from checkpoint.rng_state import capture_rng_state,restore_rng_state
ROOT=pathlib.Path(__file__).resolve().parents[1]
P={'artifact_kind':'CPU_NATIVE_INTERFACE_FIXTURE','original_data_used':False}

class Base(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(dir=ROOT/'artifacts',prefix='native-cpu-');self.d=pathlib.Path(self.t.name)
        random.seed(43);np.random.seed(43);torch.random.default_generator.manual_seed(43)
    def tearDown(self):
        set_active(None);self.assertFalse(torch.cuda.is_initialized());self.t.cleanup()
    def save(self,bundle=None,**kw):
        path=self.d/'state';m=save_state(fixture_bundle() if bundle is None else bundle,path,provenance=P,**kw);return path,m
    def ctrl(self,D=1,**kw):return NativeControl(D,self.d,**kw)

class SnapshotTests(Base):
    def test_restore_cannot_execute_custom_constructor(self):
        x=object.__new__(NoConstructorFixture);x.cache=torch.arange(3.)
        p,m=self.save({'x':x});dst,_=load_state(p);self.assertTrue(torch.equal(dst['x'].cache,x.cache))
    def test_global_RNG_roundtrip_python_numpy_and_torch(self):
        bundle={'rng':capture_rng_state()};p,m=self.save(bundle)
        expected=(random.random(),np.random.rand(),torch.rand(5))
        loaded,_=load_state(p);restore_rng_state(loaded['rng']);actual=(random.random(),np.random.rand(),torch.rand(5))
        self.assertEqual(expected[0],actual[0]);self.assertEqual(expected[1],actual[1]);self.assertTrue(torch.equal(expected[2],actual[2]))
    def test_wrong_C0_state_SHA_rejected(self):
        p,m=self.save()
        with self.assertRaises(ControlError):load_state(p,expected_sha='0'*64)
    def test_roundtrip_entire_object_fields(self):
        p,m=self.save();a,_=load_state(p);self.assertIs(a['tracker'],a['same_tracker']);self.assertIs(a['tracker'].self_reference,a['tracker'])
        self.assertEqual(set(vars(a['tracker'])),set(vars(FixtureObject())))
    def test_model_buffers_modes_and_custom_cache(self):
        src=fixture_bundle();p,m=self.save(src);dst,_=load_state(p)
        self.assertFalse(dst['tracker'].model.training);self.assertTrue(dst['tracker'].model.layer.training)
        self.assertTrue(torch.equal(src['tracker'].model.scratch,dst['tracker'].model.scratch))
        self.assertTrue(torch.equal(src['tracker'].model.custom_cache['position'],dst['tracker'].model.custom_cache['position']))
        self.assertTrue(torch.equal(src['tracker'].model(src['input']),dst['tracker'].model(dst['input'])))
    def test_storage_alias_offset_stride_and_object_alias(self):
        p,m=self.save();a=load_state(p)[0]['tracker'];self.assertIs(a.view,a.same_view)
        self.assertEqual(a.view.storage_offset(),7);self.assertEqual(a.transpose.stride(),(1,6))
        a.view[0,0]=99;self.assertEqual(a.cache[1,1],99);self.assertEqual(a.corr_pyramid[0][1,1],99)
    def test_bound_method_is_rebound_to_restored_owner(self):
        p,_=self.save();a=load_state(p)[0]['tracker'];self.assertIs(a.update_op.__self__,a.model)
    def test_explicit_generator_next_draw_matches(self):
        src=fixture_bundle();p,_=self.save(src);dst=load_state(p)[0]
        self.assertTrue(torch.equal(torch.rand(7,generator=src['tracker'].generator),torch.rand(7,generator=dst['tracker'].generator)))
    def test_reencoding_matches_manifest_nodes(self):
        p,m=self.save();a,_=load_state(p);enc=ObjectEncoder();tree=enc.encode(a)
        self.assertEqual(tree,m['root']);self.assertEqual(enc.nodes,m['nodes'])
    def test_independent_process_exit_and_restore(self):
        # Capture process exits before the separate restore process starts.
        capture="from native_control.snapshot import save_state;from native_control.cpu_fixtures import fixture_bundle;import pathlib,json,os; m=save_state(fixture_bundle(),pathlib.Path(__import__('sys').argv[1]),provenance="+repr(P)+");print(json.dumps({'pid':os.getpid(),'sha':m['state_sha256']}))"
        restore="from native_control.snapshot import load_state;import json,os,sys; x,m=load_state(sys.argv[1],expected_sha=sys.argv[2]); print(json.dumps({'pid':os.getpid(),'sha':m['state_sha256'],'next':x['tracker'].loop_cursor['next_input_index'],'alias':x['tracker'].view is x['tracker'].same_view}))"
        env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT))
        p=subprocess.run([sys.executable,'-B','-c',capture,str(self.d/'cross')],cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
        self.assertEqual(p.returncode,0,p.stderr);first=json.loads(p.stdout)
        q=subprocess.run([sys.executable,'-B','-c',restore,str(self.d/'cross'),first['sha']],cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
        self.assertEqual(q.returncode,0,q.stderr);second=json.loads(q.stdout)
        self.assertNotEqual(first['pid'],second['pid']);self.assertEqual(second['next'],18);self.assertTrue(second['alias'])
    def test_new_unknown_attribute_is_not_silently_omitted(self):
        b=fixture_bundle();b['tracker'].new_native_cache=object()
        with self.assertRaises(ControlError):self.save(b)
        self.assertFalse((self.d/'state').exists())
    def test_service_must_be_explicitly_rebound(self):
        service=object();b=fixture_bundle();b['tracker'].service=service;p,m=self.save(b,services={'printer':service})
        with self.assertRaises(ControlError):load_state(p)
        replacement=object();dst,_=load_state(p,services={'printer':replacement});self.assertIs(dst['tracker'].service,replacement)
    def test_corrupt_payload_fails_before_load(self):
        p,m=self.save();f=next(p.glob('*.pt'));f.write_bytes(f.read_bytes()[:-1]+b'!')
        with self.assertRaises(ControlError):load_state(p)
    def test_manifest_corruption_fails(self):
        p,_=self.save();m=json.loads((p/'manifest.json').read_bytes());m['root']={};(p/'manifest.json').write_text(json.dumps(m))
        with self.assertRaises(ControlError):load_state(p)
    def test_existing_C0_is_immutable(self):
        p,m=self.save();before=file_sha(p/'manifest.json')
        with self.assertRaises(ControlError):save_state({},p,provenance=P)
        self.assertEqual(before,file_sha(p/'manifest.json'))
    def test_unsealed_checkpoint_is_rejected(self):
        p,_=self.save();(p/'COMPLETE.json').unlink()
        with self.assertRaises(ControlError):load_state(p)
    def test_native_provenance_cannot_bypass_live_barrier(self):
        with self.assertRaises(ControlError):save_state({},self.d/'real',provenance={'artifact_kind':'NATIVE_C0'})
    def test_disk_insufficient_rejected_before_creating_checkpoint(self):
        with patch('native_control.snapshot.require_space',side_effect=ControlError('DISK')):
            with self.assertRaises(ControlError):self.save()
        self.assertFalse((self.d/'state').exists())
    def test_cpu_shared_storage_is_preserved(self):
        x=torch.arange(12).share_memory_();p,m=self.save({'x':x,'v':x[3:]});y=load_state(p)[0]
        self.assertTrue(y['x'].is_shared());self.assertTrue(y['v'].is_shared());self.assertEqual(y['v'].storage_offset(),3)
    def test_empty_scalar_half_bool_and_nonfinite_values(self):
        b={'empty':torch.empty(0),'scalar':torch.tensor(3.),'half':torch.ones(3,dtype=torch.float16),'bool':torch.tensor([True]),'nan':float('nan'),'inf':float('inf'),'slice':slice(3,None,8)}
        p,_=self.save(b);dst=load_state(p)[0];self.assertEqual(dst['scalar'].item(),3);self.assertTrue(np.isnan(dst['nan']));self.assertEqual(dst['slice'],slice(3,None,8))
    def test_numpy_and_non_string_dictionary_keys(self):
        b={'n':np.arange(12,dtype=np.float64).reshape(3,4).copy(),'dict':{(1,2):np.float32(3)}};p,m=self.save(b);dst=load_state(p)[0]
        np.testing.assert_array_equal(b['n'],dst['n']);self.assertEqual(dst['dict'][(1,2)].dtype,np.dtype('float32'))
    def test_numpy_view_fails_instead_of_losing_alias(self):
        with self.assertRaises(ControlError):self.save({'view':np.arange(12)[::2]})
    def test_nonempty_forward_hook_fails_closed(self):
        b=fixture_bundle();b['tracker'].model.register_forward_hook(lambda *a:None)
        with self.assertRaises(ControlError):self.save(b)
    def test_all_full_capacity_storage_is_counted(self):
        b={'video':torch.zeros(500,4,8),'visible_view':torch.ones(20)};inv=state_inventory(b)
        self.assertEqual(inv['storage_bytes'],500*4*8*4+20*4)

def header(schedule='S1'):
    return {'c0_sha256':'c'*64,'init_D':0,'W':1,'U':1,'max_rgb':80,'schedule':schedule,'producer_D':1 if schedule=='S1' else 0}

class JournalTests(Base):
    def make(self):
        p=self.d/'s1.jsonl';j=NativeJournal(p,header())
        for rgb in range(19,81):
            j.point('frame.begin',rgb,{'k':[1,8,18]},{'index':rgb-1})
            if rgb==19:j.point('decision',19,{'k':[1,8,18]},{'admit':True},select=True)
            j.point('frame.end',rgb,{'k':[1,8,18]},{'next_input_index':rgb})
        j.seal();return p
    def test_prefix_schedule_seals_without_fabricated_export(self):
        p=self.make();s=read_schedule(p);self.assertEqual(s['footer']['termination'],'PREFIX_RGB080');self.assertEqual(len(s['events']),125)
    def test_cross_D_can_select_same_decision_from_new_natural_proposal(self):
        p=self.make();j=NativeJournal(self.d/'replay.jsonl',header(),mode='replay',source=p)
        j.point('frame.begin',19,{'k':[1,8,18]},{'index':18})
        self.assertTrue(j.point('decision',19,{'k':[1,8,18]},{'admit':False},select=True)['admit'])
        for e in j.source['events'][2:]:j.point(e['kind'],e['rgb'],e['context'],e['payload'])
        j.seal()
    def test_graph_mismatch_latches_stop(self):
        p=self.make();j=NativeJournal(self.d/'replay',header(),mode='replay',source=p)
        with self.assertRaises(ControlError):j.point('frame.begin',19,{'k':[1,7,18]},{'index':18})
        with self.assertRaises(ControlError):j.point('frame.begin',19,{'k':[1,8,18]},{'index':18})
        j.abort()
    def test_mismatched_BA_order_fails(self):
        p=self.make();j=NativeJournal(self.d/'replay',header(),mode='replay',source=p)
        with self.assertRaises(ControlError):j.point('ba.begin',19,{'k':[1,8,18]},{'index':18})
        j.abort()
    def test_partial_journal_is_not_a_schedule(self):
        p=self.d/'partial';j=NativeJournal(p,header());j.abort()
        with self.assertRaises(ControlError):read_schedule(p)
    def test_event_tamper_fails_hash(self):
        p=self.make();raw=p.read_text().replace('"admit":true','"admit":false');p.write_text(raw)
        with self.assertRaises(ControlError):read_schedule(p)
    def test_no_RGB081_is_admitted(self):
        j=NativeJournal(self.d/'bad',header())
        with self.assertRaises(ControlError):j.point('frame.begin',81,{},{});
        j.abort()
    def test_unconsumed_events_cannot_seal(self):
        p=self.make();j=NativeJournal(self.d/'replay',header(),mode='replay',source=p)
        with self.assertRaises(ControlError):j.seal()
        j.abort()
    def test_wrong_common_C0_rejected(self):
        p=self.make();h=header();h['c0_sha256']='d'*64
        with self.assertRaises(ControlError):NativeJournal(self.d/'replay',h,mode='replay',source=p)

class ControlBoundaryTests(Base):
    def test_native_video_slot_map_mismatch_fails_before_capture(self):
        c=self.ctrl();c.rgb=19;c.nodes=['kf:001','kf:018']
        t=types.SimpleNamespace(video=types.SimpleNamespace(counter=types.SimpleNamespace(value=2),timestamp=torch.tensor([0.,16.])))
        with self.assertRaises(ControlError):c.frame_end(t,None,{'next_input_index':19})
    def test_no_capture_before_24_updates(self):
        c=self.ctrl();f=types.SimpleNamespace(is_initialized=True,t1=12,warmup=12)
        with self.assertRaises(ControlError):c.initialization_done(f)
    def test_actual_initialization_boundary_recorded(self):
        c=self.ctrl();c.rgb=18;c.init_counts=dict.fromkeys(('frontend_init_neighborhood','frontend_init_proximity','frontend_init_second'),8)
        c.initialization_done(types.SimpleNamespace(is_initialized=True,t1=12,warmup=12));self.assertTrue(c.initialized)
    def test_capture_only_at_frame_tail_before_next_read(self):
        calls=[];c=self.ctrl(capture_callback=lambda *x:calls.append(x[2]['next_input_index']));c.initialized=True;c.rgb=18
        with self.assertRaises(PrefixComplete):c.frame_end(None,None,{'next_input_index':18})
        self.assertEqual(calls,[18])
    def test_prefix_ends_at_80_without_final_BA(self):
        c=self.ctrl();c.rgb=80
        with self.assertRaises(PrefixComplete):c.frame_end(None,None,{'next_input_index':80})
    def test_frame_order_mismatch_stops(self):
        c=self.ctrl()
        with self.assertRaises(ControlError):c.frame_begin(18,19)
    def test_depth_only_in_scoped_native_phases(self):
        c=self.ctrl(D=0);self.assertFalse(c.depth_flag('frontend_init_second',True));self.assertFalse(c.depth_flag('frontend_local_predecision',True));self.assertTrue(c.depth_flag('filler_pose_only',True))
        c.D=1;self.assertTrue(c.depth_flag('frontend_local_predecision',True));self.assertFalse(c.depth_flag('frontend_init_neighborhood',True))
    def test_initialization_retains_native_UBA_template(self):
        c=self.ctrl();set_active(c);v=types.SimpleNamespace(metric_depth_reg=True,uncertainty_aware=True,enable_affine_transform=True,enable_bidirectional_uncer=False)
        self.assertEqual(selected_flags(None,None,'frontend_init_neighborhood',v,False,True,False),(False,False,True))
    def test_local_W_and_U_are_not_redefined(self):
        c=self.ctrl(D=0);set_active(c);v=types.SimpleNamespace(metric_depth_reg=True,uncertainty_aware=True,enable_affine_transform=True,enable_bidirectional_uncer=False,cfg={'tracking':{'uncertainty_params':{'gamma_depth':0.01},'frontend':{'enable_loop':False}}})
        self.assertEqual(selected_flags(None,'frontend_local_predecision','frontend_local_predecision',v,False,True,True),(False,True,True))
    def test_mismatched_stage_cannot_apply_D(self):
        c=self.ctrl();set_active(c);v=types.SimpleNamespace(metric_depth_reg=True)
        with self.assertRaises(ControlError):selected_flags(None,'frontend_local_retained','final_global',v,False,True,True)
    def test_pending_operation_cannot_checkpoint(self):
        c=self.ctrl();c.begin('native.ba',{})
        with self.assertRaises(ControlError):c.snapshot_discrete()

class BarrierTests(Base):
    def test_writer_acknowledges_after_sync_and_resumes(self):
        barrier=WriterBarrier(multiprocessing.get_context('spawn'));calls=[];stop=threading.Event()
        def writer():
            while not stop.is_set():barrier.pause_point(lambda:calls.append('synced'));time.sleep(.001)
        t=threading.Thread(target=writer);t.start()
        try:
            with barrier.quiesce(timeout=2):self.assertTrue(barrier.acknowledged.is_set());self.assertEqual(calls,['synced'])
        finally:stop.set();barrier.request.clear();t.join(timeout=3)
        self.assertFalse(t.is_alive())
    def test_missing_writer_times_out_before_snapshot(self):
        barrier=WriterBarrier(multiprocessing.get_context('spawn'))
        with self.assertRaises(ControlError):
            with barrier.quiesce(timeout=.01):self.fail('No writer must not admit capture')

class NativePythonBodyTests(Base):
    def setUp(self):
        super().setUp()
        self.mock_observer=types.SimpleNamespace(stage='frontend_local_predecision')
        self.module_patch=patch.dict(sys.modules,{'task003_observer':types.SimpleNamespace(recorder=lambda:self.mock_observer)})
        self.module_patch.start()
    def tearDown(self):
        self.module_patch.stop();super().tearDown()
    def graph(self,D=1,controller=None):
        c=controller or self.ctrl(D=D);set_active(c)
        c.nodes=['kf:001','kf:008','kf:018']
        cls=load_class(ROOT/'source_candidate','src/factor_graph.py','FactorGraph')
        install_factor_graph(cls);v=FakeVideo(D);g=cls(v,fake_update,device='cpu',max_factors=40)
        return c,g,v
    def test_native_graph_add_has_stable_RGB_edge_identity(self):
        c,g,v=self.graph();g.add_factors([0,1],[1,2]);ctx=c.context()
        rows=ctx['graphs'][0]['edges'];self.assertEqual(rows[0]['source'],'kf:001');self.assertEqual(rows[1]['target'],'kf:018')
        self.assertEqual(len({r['edge_id'] for r in rows}),2)
    def test_native_rm_factors_moves_same_edge_to_inactive(self):
        c,g,v=self.graph();g.add_factors([0,1],[1,2]);eid=c.context()['graphs'][0]['edges'][0]['edge_id']
        g.rm_factors(torch.tensor([True,False]),store=True)
        rows=c.context()['graphs'][0]['edges'];inactive=[x for x in rows if x['state']=='inactive']
        self.assertEqual(inactive[0]['edge_id'],eid);self.assertEqual(len(g.ii),1)
    def test_native_graph_update_recomputes_continuous_state(self):
        c,g,v=self.graph(D=0);g.add_factors([0,1],[1,2]);before=v.disps.clone();g.update(1,3,use_inactive=True)
        self.assertFalse(torch.equal(before,v.disps));self.assertEqual(g.age.tolist(),[1,1]);self.assertEqual(c.operation_stack,[])
    def test_unrecorded_graph_mutation_is_rejected(self):
        c,g,v=self.graph();g.add_factors([0],[1]);g.ii=torch.tensor([2])
        with self.assertRaises(ControlError):c.context()
    def test_unrecorded_edge_age_change_is_rejected(self):
        c,g,v=self.graph();g.add_factors([0],[1]);g.age+=1
        with self.assertRaises(ControlError):c.context()
    def test_native_graph_clear_is_recorded(self):
        c,g,v=self.graph();g.add_factors([0],[1]);g.clear_edges();self.assertEqual(c.context()['graphs'][0]['edges'],[])
    def test_native_tail_keyframe_removal_keeps_stable_remaining_ids(self):
        c,g,v=self.graph();g.add_factors([0,1],[1,2]);g.rm_keyframe(2)
        self.assertEqual(c.nodes,['kf:001','kf:008']);self.assertEqual(g.ii.tolist(),[0]);self.assertEqual(g.jj.tolist(),[1])
        self.assertEqual(c.context()['graphs'][0]['edges'][0]['target'],'kf:008')
    def test_unaudited_non_tail_removal_stops_before_mutation(self):
        c,g,v=self.graph();g.add_factors([0],[1]);before=c.context()
        with self.assertRaises(ControlError):g.rm_keyframe(0)
        self.assertEqual(c.context(),before)
    def test_impossible_native_edge_cannot_be_scheduled(self):
        c,g,v=self.graph()
        with self.assertRaises(ControlError):g.add_factors([0],[7])
    def test_native_cross_D_forces_graph_events_but_not_depth(self):
        # Both arms execute actual FactorGraph Python bodies. Extension and CNN
        # math is a declared CPU fixture, and not evidence of real GPU replay.
        a=self.d/'record';b=self.d/'replay';a.mkdir();b.mkdir()
        def run(D,out,source=None,schedule='S1'):
            c=NativeControl(D,out);set_active(c);c.nodes=['kf:001','kf:008','kf:018']
            cls=load_class(ROOT/'source_candidate','src/factor_graph.py','FactorGraph');install_factor_graph(cls)
            v=FakeVideo(D);g=cls(v,fake_update,device='cpu',max_factors=40)
            # The graph exists in the common synthetic C0, before journaling.
            journal=NativeJournal(out/'schedule.jsonl',header(schedule),mode='replay' if source else 'record',source=source);c.journal=journal
            for rgb in range(19,81):
                c.frame_begin(rgb-1,rgb-1)
                if rgb==19:
                    g.add_factors([0,1] if D else [1,2],[1,2] if D else [2,0])
                    g.update(1,3,use_inactive=True)
                    g.rm_factors(torch.tensor([True,False]) if D else torch.tensor([False,True]),store=True)
                try:c.frame_end(None,None,{'next_input_index':rgb})
                except PrefixComplete:
                    if rgb!=80:raise
            set_active(None);return c,g,v
        c,g,v=run(1,a);d,h,w=run(0,b,a/'schedule.jsonl')
        self.assertEqual(c.context(),d.context());self.assertFalse(torch.equal(v.disps,w.disps))
        self.assertEqual(g.ii.tolist(),h.ii.tolist());self.assertEqual(g.ii_inac.tolist(),h.ii_inac.tolist())
        a0=self.d/'record_S0';b1=self.d/'replay_S0';a0.mkdir();b1.mkdir()
        c0,g0,v0=run(0,a0,schedule='S0');c1,g1,v1=run(1,b1,a0/'schedule.jsonl',schedule='S0')
        self.assertEqual(c0.context(),c1.context());self.assertFalse(torch.equal(v0.disps,v1.disps))
        self.assertEqual(g0.ii.tolist(),g1.ii.tolist());self.assertEqual(g0.ii_inac.tolist(),g1.ii_inac.tolist())
    def test_native_CUDA_BA_call_arguments_preserved_static(self):
        def calls(path):
            return [ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(path.read_text())) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='droid_backends']
        self.assertEqual(calls(ROOT/'source_before/src/depth_video.py'),calls(ROOT/'source_candidate/src/depth_video.py'))
    def test_tracker_frame_end_hook_after_all_original_frame_work(self):
        s=(ROOT/'source_candidate/src/tracker.py').read_text();self.assertLess(s.index('self.frontend.initialize_second_stage'),s.index('task004c().frame_end('))
        self.assertLess(s.index('self.printer.update_pbar()'),s.index('task004c().frame_end('));self.assertIn('native_resume["next_input_index"]',s)
    def test_native_Final_BA_call_path_keeps_7_then_12_and_restores_D(self):
        c=self.ctrl();set_active(c);calls=[]
        observer=types.SimpleNamespace(boundary=lambda *a:None)
        class MockBA:
            def __init__(self,net,video,cfg):self.video=video
            def dense_ba(self,steps,**kw):calls.append((steps,self.video.metric_depth_reg,kw['enable_udba']))
        timer=types.SimpleNamespace(section=lambda *a:(lambda f:f))
        cls=load_class(ROOT/'source_candidate','src/slam.py','SLAM',{'BaseDataset':object,'timer':timer,
             'task003':lambda:observer,'task004_policy':lambda:types.SimpleNamespace(final_phases=2),
             'Backend':MockBA,'FontColor':types.SimpleNamespace(TRACKER='x')})
        slam=cls.__new__(cls);slam.video=types.SimpleNamespace(metric_depth_reg=True);slam.droid_net=None
        slam.cfg={'tracking':{'frontend':{'enable_opt_dyn_mask':True}}};slam.printer=types.SimpleNamespace(print=lambda *a:None)
        with patch.object(torch.cuda,'empty_cache',lambda:None):slam.backend()
        self.assertEqual(calls,[(7,False,True),(12,False,True)]);self.assertTrue(slam.video.metric_depth_reg)
    def test_native_Filler_body_keeps_12_motion_only_updates_and_returns_counter(self):
        c=self.ctrl();set_active(c);calls=[]
        class SE3:
            def __init__(self,data):self.data=data
            def __getitem__(self,x):return SE3(self.data[x])
            def __mul__(self,x):return SE3(self.data+x.data)
            def inv(self):return SE3(-self.data)
            def log(self):return self.data
            @staticmethod
            def exp(w):return SE3(w)
        class G:
            corr_impl='volume';max_factors=75
            def __init__(self,video,update):self.video=video
            def add_factors(self,a,b):calls.append(('edge',a.tolist(),b.tolist()))
            def update(self,a,b,**kw):calls.append(('update',a,b,kw))
        class V:
            def __init__(self):
                self.counter=types.SimpleNamespace(value=3);self.timestamp=torch.tensor([0.,8.,17.,0.,0.,0.]);self.poses=torch.zeros(6,7);self.uncertainties=torch.ones(6,4,4)
            def __setitem__(self,index,item):self.timestamp[index]=item[0];self.poses[index]=item[2]
        observer=types.SimpleNamespace(context=lambda *a:None,filler_begin=lambda *a:None,filler_step=lambda *a:None,filler_end=lambda *a:None)
        # No graphs are created in the numerical fixture. The actual Filler
        # hook still verifies batch, anchors, capacity and counter lifecycle.
        main=types.SimpleNamespace(corr_impl='volume',max_factors=75,ii=None,jj=None,ii_inac=None,jj_inac=None,ii_bad=None,jj_bad=None)
        c.graph_created(main);c.tracker=types.SimpleNamespace(frontend=types.SimpleNamespace(graph=main))
        cls=load_class(ROOT/'source_candidate','src/trajectory_filler.py','PoseTrajectoryFiller',{'SE3':SE3,'FactorGraph':G,'BaseDataset':object,'task003':lambda:observer})
        filler=cls.__new__(cls);filler.video=V();filler.device='cpu';filler.uncertainty_aware=True;filler.update=None
        filler.MEAN=torch.zeros(3,1,1);filler.STDV=torch.ones(3,1,1)
        filler._PoseTrajectoryFiller__feature_encoder=lambda x:torch.zeros(len(x),1,128,4,4)
        c.nodes=['kf:001','kf:009','kf:018']
        with patch.object(torch.Tensor,'cuda',lambda x,*a,**k:x):
            result=filler._PoseTrajectoryFiller__fill([1,2],[torch.ones(1,3,32,32),torch.ones(1,3,32,32)],None,[torch.ones(4),torch.ones(4)],None)
        self.assertEqual(len([r for r in calls if r[0]=='update']),12)
        self.assertTrue(all(r[3]['motion_only'] and not r[3]['enable_update_uncer'] for r in calls if r[0]=='update'))
        self.assertEqual(filler.video.counter.value,3);self.assertEqual(len(c.nodes),3);self.assertEqual(result[0].data.shape,(2,7))

class BoundedRunnerTests(Base):
    def test_no_mode_can_request_487(self):
        with self.assertRaises(ValueError):validate_mode('record_S1',487)
    def test_formal_B1_is_not_a_smoke_mode(self):
        with self.assertRaises(ValueError):validate_mode('B1',80)
    def test_smoke_plan_does_not_import_torch_or_models(self):
        code="import sys;from runner.run_native_smoke import main;main(['--mode','capture','--cpu-report','unused']);print('TORCH_IMPORTED', 'torch' in sys.modules)"
        q=subprocess.run([sys.executable,'-B','-c',code],cwd=ROOT,capture_output=True,text=True,timeout=30,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''))
        self.assertEqual(q.returncode,0,q.stderr);self.assertIn('TORCH_IMPORTED False',q.stdout)
    def test_all_modes_are_bounded_and_named(self):
        for mode in ('capture','restore_check','record_S1','record_S0','replay_D0_S1','replay_D1_S0'):self.assertTrue(validate_mode(mode,80))
