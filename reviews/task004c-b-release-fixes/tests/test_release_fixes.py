import importlib.util,json,os,pathlib,random,shutil,sys,tempfile,types,unittest
import importlib.metadata
from unittest.mock import patch
import numpy as np
import torch
import torch.multiprocessing as mp
from control_common import ControlError
from native_control.runtime import NativeControl,set_active
from native_control.install import selected_flags
from native_control.file_backed import FileArena,descriptor_for,validate_descriptor,cpu_zeros
from native_control.snapshot import save_state,load_state,prepare_state,save_prepared_state
from native_control.storage_budget import make_budget,check_budget
from native_control.admission import cpu_storage_admission
from tests.file_support import reader,info,tensor_sha

ROOT=pathlib.Path(__file__).resolve().parents[1]
P={'artifact_kind':'CPU_NATIVE_INTERFACE_FIXTURE','seed':43,'not_native_C0':True}

def video():return types.SimpleNamespace(metric_depth_reg=True,uncertainty_aware=True,enable_affine_transform=True,
    enable_bidirectional_uncer=False,cfg={'tracking':{'uncertainty_params':{'gamma_depth':.01},'frontend':{'enable_loop':False}}})

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'artifacts',prefix='release-cpu-');self.d=pathlib.Path(self.tmp.name)
        random.seed(43);np.random.seed(43);torch.random.default_generator.manual_seed(43);self.strategy=mp.get_sharing_strategy()
    def tearDown(self):
        set_active(None);mp.set_sharing_strategy(self.strategy);self.assertFalse(torch.cuda.is_initialized());self.tmp.cleanup()
    def ctrl(self,D=0):
        c=NativeControl(D,self.d);set_active(c);return c
    def child(self,payload,write=False):
        ctx=mp.get_context('spawn');recv,send=ctx.Pipe(False);p=ctx.Process(target=reader,args=(send,payload,'CPU_SHARED_READER',write));p.start();send.close()
        self.assertTrue(recv.poll(45),'Child did not reply');r=recv.recv();p.join(timeout=20)
        self.assertFalse(p.is_alive());self.assertEqual(p.exitcode,0,r);self.assertEqual(r.get('exit_code'),0,r)
        self.assertFalse(r['cuda_initialized']);return r

class ScopeGuardTests(Base):
    def test_missing_phase_marker_stops_both_local_stages(self):
        self.ctrl()
        for stage in ('frontend_local_predecision','frontend_local_retained'):
            with self.subTest(stage=stage),self.assertRaises(ControlError):selected_flags(None,None,stage,video(),False,True,True)
    def test_incorrect_phase_marker_stops(self):
        self.ctrl()
        for phase,stage in [('frontend_local_predecision','frontend_local_retained'),('frontend_local_retained','final_global'),('bad','bad')]:
            with self.subTest(phase=phase,stage=stage),self.assertRaises(ControlError):selected_flags(None,phase,stage,video(),False,True,True)
    def test_invalid_motion_only_local_stops(self):
        self.ctrl()
        with self.assertRaises(ControlError):selected_flags(None,'frontend_local_predecision','frontend_local_predecision',video(),True,True,True)
    def test_motion_only_initialization_cannot_change_D(self):
        self.ctrl()
        for stage in ('frontend_init_neighborhood','frontend_init_proximity','frontend_init_second'):
            with self.subTest(stage=stage),self.assertRaises(ControlError):selected_flags(None,None,stage,video(),True,True,True)
    def test_valid_initialization_D_zero_all_three_stages(self):
        self.ctrl(D=1)
        for stage in ('frontend_init_neighborhood','frontend_init_proximity','frontend_init_second'):
            self.assertEqual(selected_flags(None,None,stage,video(),False,True,False),(False,False,True))
    def test_valid_local_D_toggle_W_U_unchanged(self):
        c=self.ctrl(D=0)
        for d in (0,1):
            c.D=d
            for stage in ('frontend_local_predecision','frontend_local_retained'):
                self.assertEqual(selected_flags(None,stage,stage,video(),False,True,True),(bool(d),True,True))
    def test_nonlocal_pass_through_does_not_use_controller_D(self):
        self.ctrl(D=0);v=video()
        for stage in ('final_global','filler_pose_only','unknown_stage'):
            self.assertEqual(selected_flags(None,None,stage,v,True,False,False),(True,False,False))
    def test_all_original_vanilla_contract_failures_remain_rejected(self):
        self.ctrl()
        for field,value in [('metric_depth_reg',False),('uncertainty_aware',False),('enable_affine_transform',False),('enable_bidirectional_uncer',True)]:
            v=video();setattr(v,field,value)
            with self.subTest(field=field),self.assertRaises(ControlError):selected_flags(None,'frontend_local_predecision','frontend_local_predecision',v,False,True,True)
        for u,w in [(False,True),(True,False)]:
            with self.subTest(u=u,w=w),self.assertRaises(ControlError):selected_flags(None,'frontend_local_predecision','frontend_local_predecision',video(),False,u,w)
        for gamma,loop in [(.02,False),(.01,True)]:
            v=video();v.cfg['tracking']['uncertainty_params']['gamma_depth']=gamma;v.cfg['tracking']['frontend']['enable_loop']=loop
            with self.subTest(gamma=gamma,loop=loop),self.assertRaises(ControlError):selected_flags(None,'frontend_local_predecision','frontend_local_predecision',v,False,True,True)
    def test_rejection_equivalence_to_frozen_original_local_flags(self):
        path=ROOT/'source_candidate/task004_controls.py';spec=importlib.util.spec_from_file_location('frozen_local_flags',path);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
        m.policy=lambda:types.SimpleNamespace(local_dwu=(1,1,1));self.ctrl()
        for phase,stage,motion in [(None,'frontend_local_predecision',False),('x','x',False),('frontend_local_predecision','frontend_local_retained',False),('frontend_local_predecision','frontend_local_predecision',True)]:
            with self.assertRaises(ValueError):m.local_flags(phase,stage,video(),motion,True,True)
            with self.assertRaises(ControlError):selected_flags(m.local_flags,phase,stage,video(),motion,True,True)
    def test_disabled_controller_delegates_original_unchanged(self):
        calls=[]
        def original(*args):calls.append(args);return ('original',False,False)
        self.assertEqual(selected_flags(original,None,'other',video(),True,False,False),('original',False,False));self.assertEqual(len(calls),1)

class FileSharingTests(Base):
    def test_spawn_file_backing_values_and_aliases_preserved(self):
        arena=FileArena(self.d/'arena',floor_bytes=0);x=arena.zeros((4,6));x.copy_(torch.arange(24).reshape(4,6));v=x[1:,1:5]
        before=info(x);r=self.child({'base':x,'view':v,'same':v},write=True)
        self.assertTrue(r['alias']);self.assertTrue(r['repeated_object']);self.assertEqual(r['view']['stride'],list(v.stride()));self.assertEqual(r['view']['offset'],v.storage_offset())
        self.assertEqual(r['before']['sha256'],before['sha256']);self.assertEqual(x[0,0],91)
        self.assertEqual(r['before']['descriptor']['st_ino'],before['descriptor']['st_ino'])
        raw=torch.from_file(before['descriptor']['path'],shared=True,size=24,dtype=torch.float32);self.assertEqual(raw[0],91)
    def test_two_distinct_spawn_readers_share_the_same_file(self):
        arena=FileArena(self.d/'arena',floor_bytes=0);x=arena.zeros((8,));x.copy_(torch.arange(8))
        a=self.child({'base':x},write=True);b=self.child({'base':x})
        self.assertNotEqual(a['pid'],b['pid']);self.assertEqual(a['after']['sha256'],b['before']['sha256']);self.assertEqual(b['before']['descriptor']['st_ino'],a['before']['descriptor']['st_ino'])
    def test_global_file_system_strategy_does_not_move_owned_storage_to_shm(self):
        mp.set_sharing_strategy('file_system');a=FileArena(self.d/'arena',floor_bytes=0);x=a.zeros((64,));r=self.child({'base':x})
        self.assertIsNotNone(r['before']['descriptor']);self.assertEqual(r['before']['descriptor']['path'],descriptor_for(x.untyped_storage())['path'])
    def test_all_core_dtypes_and_transposed_strides(self):
        arena=FileArena(self.d/'arena',floor_bytes=0)
        for dtype in (torch.float32,torch.float16,torch.bfloat16,torch.float64,torch.int64,torch.uint8,torch.bool):
            with self.subTest(dtype=str(dtype)):
                x=arena.zeros((2,3),dtype=dtype);x.fill_(1);r=self.child({'base':x.T})
                self.assertEqual(r['before']['dtype'],str(dtype));self.assertEqual(r['before']['stride'],[1,3]);self.assertEqual(r['before']['sha256'],tensor_sha(x.T))
    def test_unregistered_normal_CPU_tensor_retains_Torch_sharing(self):
        x=torch.arange(4.);self.assertIsNone(descriptor_for(x.untyped_storage()));r=self.child({'base':x},write=True)
        self.assertEqual(x[0],91);self.assertIsNone(r['before']['descriptor'])
    def test_descriptor_size_change_is_rejected(self):
        a=FileArena(self.d/'arena',floor_bytes=0);x=a.zeros((16,));d=descriptor_for(x.untyped_storage());d['byte_size']+=4
        with self.assertRaises(ControlError):validate_descriptor(d)
    def test_descriptor_cannot_escape_owner_root(self):
        a=FileArena(self.d/'arena',floor_bytes=0);x=a.zeros((16,));d=descriptor_for(x.untyped_storage());d['path']=str(self.d/'outside.bin')
        with self.assertRaises(ControlError):validate_descriptor(d)
    def test_file_allocation_has_expected_physical_reservation(self):
        a=FileArena(self.d/'arena',floor_bytes=0);x=a.zeros((1024*1024,));s=pathlib.Path(descriptor_for(x.untyped_storage())['path']).stat()
        self.assertEqual(s.st_size,4*1024**2);self.assertGreaterEqual(s.st_blocks*512,s.st_size)
    def test_snapshot_restore_uses_file_backing_and_preserves_alias(self):
        a=FileArena(self.d/'a',floor_bytes=0);x=a.zeros((4,6));x.copy_(torch.arange(24).reshape(4,6));v=x[1:,1:5]
        p=self.d/'fixture';m=save_state({'x':x,'view':v,'same':v},p,provenance=P)
        restore=FileArena(self.d/'restored',floor_bytes=0);r,_=load_state(p,expected_sha=m['state_sha256'],cpu_storage_factory=restore.restore_storage)
        self.assertEqual(tensor_sha(x),tensor_sha(r['x']));self.assertIs(r['view'],r['same']);self.assertEqual(r['view'].storage_offset(),7)
        child=self.child({'base':r['x'],'view':r['view'],'same':r['same']});self.assertTrue(child['alias']);self.assertTrue(child['repeated_object'])
    def test_native_allocator_fallback_is_unchanged_without_option(self):
        with patch.dict(os.environ,{},clear=False):
            os.environ.pop('GAMECAM_FILE_BACKED_CPU_ROOT',None)
            plain=cpu_zeros('images',(2,3),dtype=torch.float32);shared=cpu_zeros('dino',(2,3),dtype=torch.float32,native_share=True)
        self.assertFalse(plain.is_shared());self.assertTrue(shared.is_shared());self.assertTrue(torch.equal(plain,shared))
    def test_native_allocator_uses_disk_when_option_enabled(self):
        with patch.dict(os.environ,{'GAMECAM_FILE_BACKED_CPU_ROOT':str(self.d/'native')}):
            x=cpu_zeros('images',(2,3),dtype=torch.float32);y=cpu_zeros('dino',(2,3),dtype=torch.float32,native_share=True)
        self.assertIsNotNone(descriptor_for(x.untyped_storage()));self.assertIsNotNone(descriptor_for(y.untyped_storage()));self.assertTrue(x.is_shared())

class ExactBudgetTests(Base):
    def test_exact_archive_size_SHA_and_checkpoint_total(self):
        bundle={'base':torch.arange(256),'view':torch.arange(33,dtype=torch.float16),'empty':torch.empty(0),'bool':torch.tensor([True])}
        plan=prepare_state(bundle,provenance=P,destination_parent=self.d);path=self.d/'checkpoint';save_prepared_state(plan,path)
        actual=sum(p.stat().st_size for p in path.iterdir())
        self.assertEqual(actual,plan['budget']['exact_checkpoint_logical_bytes'])
        for name,row in plan['manifest']['files'].items():
            self.assertEqual(row['bytes'],(path/name).stat().st_size)
    def test_zip_padding_boundary_sizes_are_counted_exactly(self):
        for size in (0,1,63,64,65,4095,4096,65537):
            with self.subTest(size=size):
                plan=prepare_state({'x':torch.zeros(size,dtype=torch.uint8)},provenance=P,destination_parent=self.d)
                path=self.d/('state'+str(size));save_prepared_state(plan,path)
                self.assertEqual(sum(p.stat().st_size for p in path.iterdir()),plan['budget']['exact_checkpoint_logical_bytes'])
    def test_full_storage_and_alias_dedup_not_only_visible_values(self):
        x=torch.arange(1024);plan=prepare_state({'a':x[:1],'b':x[5:8]},provenance=P,destination_parent=self.d)
        self.assertEqual(plan['budget']['unique_runtime_storage_bytes'],8192);self.assertEqual(len(plan['manifest']['storages']),1)
    def test_safety_floor_boundary(self):
        b=make_budget({'a':{'bytes':1025}},700,90,block_size=4096,floor_bytes=1000,retained_scratch_bytes=20,metadata_reserve_bytes=30)
        n=b['minimum_free_before_save_bytes']
        with self.assertRaises(ControlError):check_budget(self.d,b,free_bytes=n-1)
        self.assertEqual(check_budget(self.d,b,free_bytes=n)['required_free_bytes'],n)
    def test_changed_storage_after_plan_is_rejected(self):
        x=torch.ones(8);p=prepare_state({'x':x},provenance=P,destination_parent=self.d);x[0]=99
        with self.assertRaises(ControlError):save_prepared_state(p,self.d/'bad')
        self.assertFalse((self.d/'bad').exists());self.assertTrue(list(self.d.glob('.bad.staging-*/FAILED.json')))
    def test_disk_is_rechecked_for_each_write(self):
        import native_control.storage_budget as mod
        plan=prepare_state({'a':torch.ones(2),'b':torch.ones(3)},provenance=P,destination_parent=self.d)
        with patch.object(mod,'check_budget',wraps=mod.check_budget) as check:save_prepared_state(plan,self.d/'state')
        self.assertGreaterEqual(check.call_count,len(plan['manifest']['files'])+4)
    def test_mid_save_disk_loss_preserves_failure_without_sealing(self):
        import native_control.storage_budget as mod
        original=mod.check_budget;plan=prepare_state({'a':torch.ones(2),'b':torch.ones(3)},provenance=P,destination_parent=self.d)
        def fail(path,budget,**kw):
            if kw.get('remaining_files') is not None and len(kw['remaining_files'])==2:raise ControlError('Simulated external disk use')
            return original(path,budget,**kw)
        with patch.object(mod,'check_budget',side_effect=fail):
            with self.assertRaises(ControlError):save_prepared_state(plan,self.d/'bad')
        self.assertFalse((self.d/'bad').exists());self.assertTrue(list(self.d.glob('.bad.staging-*/FAILED.json')))
    def test_budget_preparation_does_not_advance_RNG(self):
        before=torch.get_rng_state().clone();prepare_state({'x':torch.ones(2)},provenance=P,destination_parent=self.d)
        self.assertTrue(torch.equal(before,torch.get_rng_state()))
    def test_modified_prepared_manifest_is_rejected_before_write(self):
        plan=prepare_state({'x':torch.ones(2)},provenance=P,destination_parent=self.d);plan['manifest']['root']={}
        with self.assertRaises(ControlError):save_prepared_state(plan,self.d/'bad')
        self.assertFalse((self.d/'bad').exists())

class StorageAdmissionTests(Base):
    def test_unvalidated_file_backend_is_not_admitted(self):
        r=cpu_storage_admission(ROOT,backend='owned_file_mmap');self.assertFalse(r['validation_passed']);self.assertIn('FILE_BACKED_CPU_VALIDATION_MISSING',r['issues'])
    def test_validated_backend_has_small_explicit_shm_and_disk_charge(self):
        import hashlib
        sha=hashlib.sha256((ROOT/'native_control/file_backed.py').read_bytes()).hexdigest()
        proof=self.d/'proof.json';proof.write_text(json.dumps({'PASS':True,'total_tensor_bytes':2246400000,'shm_delta_bytes':61440,
              'file_backed_module_sha256':sha,'torch_distribution_version':importlib.metadata.version('torch')}))
        r=cpu_storage_admission(ROOT,backend='owned_file_mmap',validation=proof)
        self.assertTrue(r['validation_passed']);self.assertEqual(r['required_shm_bytes'],64*1024**2);self.assertGreater(r['extra_data_disk_reservation_bytes'],2246400000)
    def test_stale_module_proof_does_not_lower_shm_gate_silently(self):
        proof=self.d/'bad.json';proof.write_text(json.dumps({'PASS':True,'total_tensor_bytes':2246400000,'shm_delta_bytes':0,
              'file_backed_module_sha256':'0'*64,'torch_distribution_version':importlib.metadata.version('torch')}))
        r=cpu_storage_admission(ROOT,backend='owned_file_mmap',validation=proof)
        self.assertFalse(r['validation_passed']);self.assertIn('FILE_BACKED_CPU_VALIDATION_MISMATCH',r['issues'])
    def test_original_shm_backend_keeps_original_byte_requirement(self):
        r=cpu_storage_admission(ROOT,backend='native_shm');self.assertEqual(r['required_shm_bytes'],2246400000)
