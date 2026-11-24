"""Real SummaryWriter + real frozen rebind_output; no GPU or model construction."""
import ast,copy,hashlib,json,os,pathlib,sys,tempfile,unittest
from types import SimpleNamespace as N
from unittest.mock import patch
import torch,yaml
from torch.utils.tensorboard import SummaryWriter
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
from native_control.binding import rebind_output
from gamecam_io_overlay import prepare_summary_writer,validate_rebound_output,validate_native,OutputOwnershipError
from io_import_overlay import transformed
ROOT=pathlib.Path(os.environ['GAMECAM_NATIVE_WORKSPACE'])
TOKEN=json.loads((ROOT/'evidence/CPU_STAGE_RELEASE.json').read_text())
CFG=yaml.safe_load(pathlib.Path(TOKEN['r2_config']).read_text())
assert CFG['scene']=='native' and CFG['tracking']['buffer']==500 and CFG['stride']==1

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'tests');self.root=pathlib.Path(self.tmp.name)
        self.out=self.root/'attempts'/'restore_check';self.out.mkdir(parents=True,exist_ok=False)
        self.token='TEST_ONLY_RUN_'+self.root.name
        (self.out/'LAUNCH_INTENT.json').write_text(json.dumps({'mode':'restore_check','child_token':self.token}))
        self.env=patch.dict(os.environ,{'GAMECAM_NATIVE_WORKSPACE':str(self.root),'GAMECAM_NATIVE_APPROVED_MODE':'restore_check','GAMECAM_NATIVE_ATTEMPT':str(self.out),'GAMECAM_NATIVE_INTERNAL_CHILD':self.token})
        self.env.start();self.writers=[]
    def tearDown(self):
        for w in self.writers:w.close()
        self.env.stop();self.tmp.cleanup()
    def writer(self):
        w=prepare_summary_writer(self.out,SummaryWriter);self.writers.append(w);return w
    def bundle(self):
        cfg=copy.deepcopy(CFG)
        v=N(output='old');mf=N(save_dir='old');ob=N(output='old');loop=N(output='old')
        t=N(cfg=cfg,video=v,motion_filter=mf,online_ba=ob,frontend=N(loop_closing=loop),output='old')
        return {'tracker':t,'stream':N(out='old')}
    def test_fresh_attempt_is_exclusive(self):
        with self.assertRaises(FileExistsError):self.out.mkdir(exist_ok=False)
    def test_native_created_before_real_writer(self):
        w=self.writer();self.assertEqual(pathlib.Path(w.log_dir),self.out/'native');self.assertTrue((self.out/'native/.gamecam_io_owner.json').is_file())
    def test_real_event_file_readback(self):
        w=self.writer();w.add_scalar('IO_LIFECYCLE/probe',19,19);w.flush()
        a=EventAccumulator(str(self.out/'native'));a.Reload()
        self.assertEqual(a.Scalars('IO_LIFECYCLE/probe')[0].value,19)
    def test_real_rebind_and_no_repeated_mkdir(self):
        self.writer();b=self.bundle();r=rebind_output(b,self.out)
        self.assertFalse(r['algorithm_config_changed']);self.assertEqual(validate_rebound_output(b,self.out),self.out/'native')
    def test_rebind_keeps_existing_directory_inode(self):
        self.writer();p=self.out/'native';before=p.stat().st_ino;b=self.bundle();rebind_output(b,self.out);validate_rebound_output(b,self.out)
        self.assertEqual(before,p.stat().st_ino)
    def test_owned_service_subdirectory_allowed(self):
        self.writer();(self.out/'native/traj').mkdir();(self.out/'native/traj/service.txt').write_text('owned')
        b=self.bundle();rebind_output(b,self.out);validate_rebound_output(b,self.out)
    def test_failed_attempt_is_refused(self):
        (self.out/'PROCESS_RECEIPT.json').write_text('{"exit_code":1}')
        with self.assertRaises(OutputOwnershipError):self.writer()
    def test_existing_unowned_native_refused(self):
        (self.out/'native').mkdir()
        with self.assertRaises(FileExistsError):self.writer()
    def test_native_symlink_refused(self):
        target=self.root/'elsewhere';target.mkdir();(self.out/'native').symlink_to(target,target_is_directory=True)
        with self.assertRaises((OutputOwnershipError,FileExistsError)):self.writer()
    def test_escaped_output_refused(self):
        self.writer();b=self.bundle();rebind_output(b,self.out);b['tracker'].output=str(self.root)
        with self.assertRaises(OutputOwnershipError):validate_rebound_output(b,self.out)
    def test_wrong_run_id_refused(self):
        self.writer();os.environ['GAMECAM_NATIVE_INTERNAL_CHILD']='OTHER_RUN'
        with self.assertRaises(OutputOwnershipError):validate_native(self.out,self.out/'native')
    def test_wrong_uid_refused(self):
        self.writer();p=self.out/'native';os.chown(p,1,-1)
        try:
            with self.assertRaises(OutputOwnershipError):validate_native(self.out,p)
        finally:os.chown(p,os.geteuid(),-1)
    def test_changed_owner_receipt_refused(self):
        self.writer();p=self.out/'native/.gamecam_io_owner.json';m=json.loads(p.read_text());m['run_id_sha256']='0'*64;p.write_text(json.dumps(m))
        with self.assertRaises(OutputOwnershipError):validate_native(self.out,p.parent)
    def test_nested_symlink_refused(self):
        self.writer();(self.out/'native/escape').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(OutputOwnershipError):validate_native(self.out,self.out/'native')
    def test_directory_creation_has_single_owner(self):
        self.writer()
        with self.assertRaises(FileExistsError):self.writer()
    def test_legacy_collision_reproduced_without_gpu(self):
        p=self.root/'legacy-native';w=SummaryWriter(str(p));self.writers.append(w)
        with self.assertRaises(FileExistsError):p.mkdir(parents=True,exist_ok=False)
    def test_exact_driver_diff_is_io_only(self):
        p=ROOT/'source_candidate/native_control/native_driver.py';raw=p.read_bytes();new=transformed(raw)
        self.assertNotIn('pathlib.Path(tracker.output).mkdir(parents=True,exist_ok=False)',new)
        self.assertEqual(new.count('prepare_summary_writer(out,SummaryWriter)'),1)
    def test_captured_model_class_sources_remain_immutable(self):
        m=json.loads((ROOT/'C0/manifest.json').read_text());t=json.loads((ROOT/'evidence/CPU_STAGE_RELEASE.json').read_text())
        self.assertEqual(m['provenance']['candidate_source_commit'],t['candidate_commit'])
        self.assertEqual(m['provenance']['candidate_source_tree'],t['candidate_tree'])
        for n in ('src/tracker.py','src/depth_video.py','src/factor_graph.py','native_control/snapshot.py','native_control/configdict_adapter.py','native_control/timm_format_adapter.py','native_control/metric3d_identity.py'):
            self.assertEqual(hashlib.sha256((ROOT/'source_candidate'/n).read_bytes()).hexdigest(),t['candidate_pins']['source_candidate/'+n])

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(LifecycleTests))
    report={'total':result.testsRun,'passed':result.testsRun-len(result.failures)-len(result.errors),'failures':[(str(t),s) for t,s in result.failures],'errors':[(str(t),s) for t,s in result.errors],'real_SummaryWriter':True,'scene':CFG['scene'],'real_rebind_output':True,'cuda_initialized':torch.cuda.is_initialized(),'model_initialized':False,'CPU_fixtures_are_IO_fields_only':True}
    (ROOT/'evidence/IO_CPU_TEST_REPORT.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report));sys.exit(0 if result.wasSuccessful() and not report['cuda_initialized'] else 1)
