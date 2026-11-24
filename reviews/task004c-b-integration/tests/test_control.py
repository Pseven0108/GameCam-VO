import copy,io,json,os,pathlib,random,shutil,subprocess,sys,tempfile,types,unittest
import numpy as np
import torch
from control_common import ControlError,digest,file_sha,require_space,GIB,verify_pins
from checkpoint.checkpoint_adapter import save_checkpoint,load_checkpoint,validate_checkpoint,compare_checkpoint_hashes
from checkpoint.rng_state import capture_rng_state,restore_rng_state
from checkpoint.state_schema import validate_runtime_state,ExplicitBindings
from schedule.recorder import record_schedule,ScheduleRecorder
from schedule.replay import load_schedule,replay_schedule,validate_schedule,ScheduleReplayer
from schedule.schema import FIELDS,validate_payload,validate_context
from runner.config_validation import load_and_validate
from runner.run_experiment import plan,require_approved_runtime
from runner.native_hooks import ControlHooks,common_init_depth_regularization
from runner.validate_run import validate_run
from tests.fixtures import state_fixture,provenance,header,events_fixture,ToyRuntime
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Base(unittest.TestCase):
    def setUp(self):
        random.seed(43);np.random.seed(43);torch.random.default_generator.manual_seed(43)
        self.tmp=tempfile.TemporaryDirectory(prefix='cpu-synthetic-',dir=ROOT/'artifacts');self.d=pathlib.Path(self.tmp.name)
    def tearDown(self):
        self.assertFalse(torch.cuda.is_initialized());self.tmp.cleanup()
    def save(self,state=None,name='cp'):
        p=self.d/name;save_checkpoint(state if state is not None else state_fixture(),p,provenance=provenance());return p
    def schedule(self,name='s.jsonl'):
        events,toy=events_fixture();p=self.d/name;record_schedule(p,header(),events);return p,toy
class CheckpointTests(Base):
    def test_roundtrip_source_inventory(self):
        p=self.save();state=load_checkpoint(p);self.assertTrue(validate_runtime_state(state)['valid']);self.assertTrue(validate_checkpoint(p)['valid'])
    def test_storage_alias_stride_offset_object_identity(self):
        x=torch.arange(24,dtype=torch.float32).reshape(4,6);v=x[1:,1:5];state={'base':x,'transpose':x.T,'view':v,'same_view_object':v}
        out=load_checkpoint(self.save(state));self.assertEqual(out['view'].stride(),v.stride());self.assertEqual(out['view'].storage_offset(),v.storage_offset())
        self.assertIs(out['view'],out['same_view_object']);self.assertEqual(out['base'].untyped_storage().data_ptr(),out['transpose'].untyped_storage().data_ptr())
        out['view'][0,0]=99;self.assertEqual(out['base'][1,1],99);self.assertNotEqual(x[1,1],99)
    def test_empty_scalar_bool_half_and_bytes(self):
        d={'empty':torch.zeros(0),'scalar':torch.tensor(3.),'bool':torch.tensor([True]),'half':torch.ones(2,dtype=torch.float16),'bfloat':torch.ones(2,dtype=torch.bfloat16),'bytes':b'abc','tuple':(1,2)}
        out=load_checkpoint(self.save(d));self.assertEqual(out['scalar'].item(),3);self.assertEqual(out['bytes'],b'abc');self.assertEqual(out['tuple'],(1,2))
    def test_hashes_independent_saves(self):
        s=state_fixture();a=self.save(s,'a');b=self.save(s,'b');self.assertTrue(compare_checkpoint_hashes(a,b)['same_state']);self.assertTrue(compare_checkpoint_hashes(a,b)['same_tensor_values'])
    def test_two_loads_independent(self):
        p=self.save();a=load_checkpoint(p);b=load_checkpoint(p);a['video']['disps'].zero_();self.assertFalse(torch.equal(a['video']['disps'],b['video']['disps']))
    def test_existing_snapshot_immutable(self):
        p=self.save();before=file_sha(p/'manifest.json')
        with self.assertRaises(ControlError):save_checkpoint({},p,provenance=provenance())
        self.assertEqual(file_sha(p/'manifest.json'),before)
    def test_corrupt_storage_rejected(self):
        p=self.save();f=next(p.glob('*.pt'));data=f.read_bytes();f.write_bytes(data[:-1]+bytes([data[-1]^1]))
        with self.assertRaises(ControlError):load_checkpoint(p)
    def test_missing_complete_rejected(self):
        p=self.save();(p/'COMPLETE.json').unlink()
        with self.assertRaises(ControlError):load_checkpoint(p)
    def test_unknown_python_object_rejected(self):
        with self.assertRaises(ControlError):self.save({'opaque':object()})
    def test_identity_mismatch_rejected(self):
        p=self.save()
        with self.assertRaises(ControlError):load_checkpoint(p,expected_identity={'baseline_commit':'wrong'})
    def test_native_capture_is_not_authorized(self):
        with self.assertRaises(ControlError):save_checkpoint({},self.d/'real',provenance={'artifact_kind':'NATIVE_C0'})
    def test_graph_bounds_rejected(self):
        s=state_fixture();s['graph']['ii'][0]=4
        with self.assertRaises(ControlError):validate_runtime_state(s)
    def test_missing_state_rejected(self):
        s=state_fixture();del s['motion_filter']['net']
        with self.assertRaises(ControlError):validate_runtime_state(s)
    def test_full_capacity_required(self):
        s=state_fixture();s['video']['images']=s['video']['images'][:2]
        with self.assertRaises(ControlError):validate_runtime_state(s)
    def test_binding_unknown_attribute_stops(self):
        o=types.SimpleNamespace(x=torch.zeros(2),unregistered=1)
        with self.assertRaises(ControlError):ExplicitBindings(o,['x']).capture()
    def test_cpu_binding_restore(self):
        o=types.SimpleNamespace(x=torch.zeros(2),counter=0);b=ExplicitBindings(o,['x','counter']);b.restore_cpu_in_place({'x':torch.ones(2),'counter':2});self.assertTrue(torch.equal(o.x,torch.ones(2)));self.assertEqual(o.counter,2)
    def test_rng_roundtrip(self):
        s=capture_rng_state();p=self.save(s);expected=(random.random(),np.random.normal(0,1,4),torch.rand(4));restore_rng_state(load_checkpoint(p))
        self.assertEqual(random.random(),expected[0]);np.testing.assert_array_equal(np.random.normal(0,1,4),expected[1]);self.assertTrue(torch.equal(torch.rand(4),expected[2]))
    def test_rng_context_flag_mismatch_stops(self):
        s=capture_rng_state();s['flags']['grad_enabled']=not s['flags']['grad_enabled']
        with self.assertRaises(ControlError):restore_rng_state(s)
    def test_disk_safety_floor_blocks_before_write(self):
        with self.assertRaises(ControlError):save_checkpoint({},self.d/'blocked',provenance=provenance(),free_bytes=10*GIB-1)
        self.assertFalse((self.d/'blocked').exists());self.assertFalse(list(self.d.glob('*.staging-*')))
    def test_space_boundary(self):
        self.assertEqual(require_space(self.d,1024,free_bytes=10*GIB+1024),10*GIB+1024)
        with self.assertRaises(ControlError):require_space(self.d,1025,free_bytes=10*GIB+1024)
class ScheduleTests(Base):
    def test_record_all_22_kinds(self):
        p,toy=self.schedule();s=load_schedule(p);self.assertEqual({e['event_type'] for e in s['events']},set(FIELDS));self.assertEqual(validate_schedule(p)['events'],22)
    def test_cross_D_toy_replay_keeps_own_continuous_state(self):
        p,natural=self.schedule();other=ToyRuntime(0);r=replay_schedule(p,other);self.assertTrue(r.finish());self.assertEqual(other.context(),natural.context());self.assertNotEqual(other.continuous,natural.continuous)
    def test_event_order_tamper_rejected(self):
        p,_=self.schedule();rows=p.read_text().splitlines();rows[2],rows[3]=rows[3],rows[2];p.write_text('\n'.join(rows)+'\n')
        with self.assertRaises(ControlError):load_schedule(p)
    def test_unsealed_schedule_rejected(self):
        p=self.d/'incomplete';r=ScheduleRecorder(p,header());r.abort()
        with self.assertRaises(ControlError):load_schedule(p)
    def test_precontext_mismatch_stops_and_latches(self):
        p,_=self.schedule();r=ScheduleReplayer(load_schedule(p));ctx=ToyRuntime(0).context();ctx['active_keyframe_ids'].append(99)
        with self.assertRaises(ControlError):r.select('initialization_phase',18,ctx)
        self.assertTrue(r.failed);self.assertEqual(r.index,0)
        with self.assertRaises(ControlError):r.select('initialization_phase',18,ToyRuntime(0).context())
    def test_postcontext_mismatch_stops(self):
        p,_=self.schedule();r=ScheduleReplayer(load_schedule(p));ctx=ToyRuntime(0).context();r.select('initialization_phase',18,ctx);ctx['active_keyframe_ids'].append(99)
        with self.assertRaises(ControlError):r.confirm(ctx)
        self.assertTrue(r.failed)
    def test_incomplete_event_consumption_rejected(self):
        p,_=self.schedule();r=ScheduleReplayer(load_schedule(p))
        with self.assertRaises(ControlError):r.finish()
    def test_wrong_C0_schedule_rejected(self):
        p,_=self.schedule()
        with self.assertRaises(ControlError):load_schedule(p,{'c0_sha256':'wrong'})
    def test_continuous_payload_forbidden(self):
        p={'call_id':0,'poses':[1,2,3]}
        with self.assertRaises(ControlError):validate_payload('ba_end',p)
    def test_invalid_graph_context_rejected(self):
        c=ToyRuntime(0).context();c['ordered_edges']=[{'edge_id':'bad','graph_id':'g','source':0,'target':99,'state':'active'}]
        with self.assertRaises(ControlError):validate_context(c)
    def test_hook_pairing_and_replay(self):
        p,_=self.schedule();toy=ToyRuntime(0);h=ControlHooks('replay',replayer=ScheduleReplayer(load_schedule(p)))
        for frame,kind,proposed,before,after in events_fixture()[0]:
            actual=h.before(kind,frame,proposed,toy.context());toy.apply(kind,actual);h.after(actual,toy.context())
        self.assertTrue(h.replayer.finish())
    def test_no_nested_double_consumption(self):
        p,_=self.schedule();r=ScheduleReplayer(load_schedule(p));h=ControlHooks('replay',replayer=r);ctx=ToyRuntime(0).context();h.before('initialization_phase',18,{},ctx)
        with self.assertRaises(ControlError):h.before('initialization_phase',18,{},ctx)
    def test_common_init_selector_scoped(self):
        self.assertFalse(common_init_depth_regularization('frontend_init_second',True));self.assertTrue(common_init_depth_regularization('frontend_local_predecision',True))
class RunnerTests(Base):
    def test_exact_four_yaml(self):
        lock=json.loads((ROOT/'configs/identity_lock.json').read_text());cs=[load_and_validate(ROOT/'configs'/f'{b}.yaml',lock) for b in ('B1','B2','B3','B4')]
        self.assertEqual({c['c0_ref'] for c in cs},{'artifacts/C0'});self.assertEqual([c['D'] for c in cs],[1,0,1,0])
    def test_mutated_non_target_parameter_rejected(self):
        p=self.d/'bad.yaml';p.write_text((ROOT/'configs/B1.yaml').read_text().replace('buffer: 500','buffer: 256'))
        with self.assertRaises(ControlError):load_and_validate(p,json.loads((ROOT/'configs/identity_lock.json').read_text()))
    def test_dry_run_four_arms(self):
        for b in ('B1','B2','B3','B4'):
            q=subprocess.run([sys.executable,'-B',str(ROOT/'runner/run_experiment.py'),'--experiment',b,'--dry-run'],capture_output=True,timeout=15)
            self.assertEqual(q.returncode,0,q.stderr.decode());d=json.loads(q.stdout);self.assertTrue(d['plan_valid']);self.assertFalse(d['formal_execution_ready'])
    def test_no_implicit_experiment(self):
        q=subprocess.run([sys.executable,'-B',str(ROOT/'runner/run_experiment.py'),'--dry-run'],capture_output=True,timeout=15);self.assertNotEqual(q.returncode,0)
    def test_formal_execution_guard_retained(self):
        with self.assertRaises(ControlError):require_approved_runtime({})
        with self.assertRaises(ControlError):require_approved_runtime({'formal_runs_authorized':True,'native_integration_validated':True})
    def test_real_run_cli_remains_blocked(self):
        q=subprocess.run([sys.executable,'-B',str(ROOT/'runner/run_experiment.py'),'--experiment','B1','--output-root',str(self.d/'receipts')],capture_output=True,timeout=15)
        self.assertEqual(q.returncode,2);self.assertFalse(json.loads(q.stdout)['formal_run_started'])
    def test_pin_mismatch_rejected(self):
        p=self.d/'pin';p.write_text('x')
        with self.assertRaises(ControlError):verify_pins({str(p):'0'*64})
    def test_validate_run_rejects_486_poses(self):
        p=self.d/'poses.npy';a=np.zeros((486,7));a[:,6]=1;np.save(p,a)
        r={'exit_code':0,'formal_run_started':True,'input_rgb_ids':list(range(1,488)),'policy_sha256':'p','c0_state_sha256':'c','pose_file_sha256':file_sha(p),'schedule_complete':True,'native_calls_verified':True,'status':'COMPLETE'}
        with self.assertRaises(ControlError):validate_run(r,p,r['input_rgb_ids'],expected_policy_sha='p',expected_c0_sha='c')
    def test_validate_run_accepts_only_full_matching_pose_array(self):
        p=self.d/'poses.npy';a=np.zeros((487,7));a[:,6]=1;np.save(p,a)
        r={'exit_code':0,'formal_run_started':True,'input_rgb_ids':list(range(1,488)),'policy_sha256':'p','c0_state_sha256':'c','pose_file_sha256':file_sha(p),'schedule_complete':True,'native_calls_verified':True,'status':'COMPLETE'}
        v=validate_run(r,p,r['input_rgb_ids'],expected_policy_sha='p',expected_c0_sha='c');self.assertTrue(v['valid']);self.assertFalse(v['direct_keyframe_pose_claim'])

class AdditionalBoundaryTests(Base):
    def test_real_shared_cpu_storage_roundtrip(self):
        t=torch.arange(8,dtype=torch.float32).share_memory_();p=self.save({'t':t,'view':t[2:]});out=load_checkpoint(p)
        self.assertTrue(out['t'].is_shared());self.assertTrue(out['view'].is_shared());self.assertEqual(out['view'].storage_offset(),2)
    def test_atomic_manifest_failure_retains_partial_not_sealed(self):
        from unittest.mock import patch
        good=self.save(name='good');before=file_sha(good/'manifest.json')
        with patch('checkpoint.checkpoint_adapter.exclusive_json',side_effect=OSError('synthetic disk write failure')):
            with self.assertRaises(OSError):self.save(name='broken')
        self.assertFalse((self.d/'broken').exists());self.assertEqual(file_sha(good/'manifest.json'),before)
        partials=list(self.d.glob('.broken.staging-*'));self.assertEqual(len(partials),1)
        with self.assertRaises(ControlError):load_checkpoint(partials[0])
    def test_snapshot_tail_bytes_preserved(self):
        base=torch.arange(100,dtype=torch.float32);view=base[:3];p=self.save({'view':view});out=load_checkpoint(p)
        self.assertEqual(out['view'].untyped_storage().nbytes(),400);self.assertTrue(torch.equal(out['view'],view))
    def test_duplicate_yaml_key_rejected(self):
        p=self.d/'dup.yaml';p.write_text((ROOT/'configs/B1.yaml').read_text()+'D: 1\n')
        with self.assertRaises(ControlError):load_and_validate(p,json.loads((ROOT/'configs/identity_lock.json').read_text()))
    def test_unpaired_ba_event_rejected(self):
        from schedule.schema import EventLifecycle
        life=EventLifecycle()
        with self.assertRaises(ControlError):life.accept(19,'ba_end',{'call_id':999})
    def test_unpaired_final_ba_rejected(self):
        from schedule.schema import EventLifecycle
        with self.assertRaises(ControlError):EventLifecycle().accept(19,'final_ba_end',{'stage':1,'metric_depth_reg_restored':True})
    def test_filler_over_capacity_rejected(self):
        from schedule.schema import EventLifecycle
        with self.assertRaises(ControlError):EventLifecycle().accept(19,'filler_batch_begin',{'batch_id':0,'rgb_ids':[19],'slots':[500],'anchor_left':[0],'anchor_right':[1]})
    def test_events_after_export_rejected(self):
        from schedule.schema import EventLifecycle
        life=EventLifecycle();life.accept(1,'export_complete',{'pose_count':0,'rgb_ids':[]})
        with self.assertRaises(ControlError):life.accept(2,'frame_begin',{'input_index':1,'rgb_id':2,'timestamp_token':'2'})
    def test_recorder_disconnected_context_stops(self):
        p=self.d/'badrecord';r=ScheduleRecorder(p,header());e=events_fixture()[0][0];r.append(*e);bad=copy.deepcopy(e);bad[3]['active_keyframe_ids'].append(99)
        with self.assertRaises(ControlError):r.append(*bad)
        self.assertTrue(r.closed)
        with self.assertRaises(ControlError):load_schedule(p)
    def test_recorder_missing_export_not_sealed(self):
        p=self.d/'noexport';r=ScheduleRecorder(p,header());r.append(*events_fixture()[0][0])
        with self.assertRaises(ControlError):r.seal()
        with self.assertRaises(ControlError):load_schedule(p)
    def test_hook_payload_failure_latches(self):
        p,_=self.schedule();r=ScheduleReplayer(load_schedule(p));h=ControlHooks('replay',replayer=r);ctx=ToyRuntime(0).context();p=h.before('initialization_phase',18,{},ctx);p['init_D']=1
        with self.assertRaises(ControlError):h.after(p,ctx)
        self.assertTrue(h.failed);self.assertTrue(r.failed)
    def test_duplicate_native_call_id_rejected(self):
        from schedule.schema import EventLifecycle
        life=EventLifecycle();p=events_fixture()[0][6][2];life.accept(19,'ba_begin',p);life.accept(19,'ba_end',{'call_id':24})
        with self.assertRaises(ControlError):life.accept(19,'ba_begin',p)
