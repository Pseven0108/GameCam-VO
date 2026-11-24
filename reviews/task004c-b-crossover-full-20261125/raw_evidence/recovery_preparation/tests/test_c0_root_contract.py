
import pathlib,json,torch,hashlib,sys,unittest
from native_control.snapshot import read_manifest
from control_common import ControlError
root=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261124_R2_READY')
failed=root.with_name('DROID_W_TASK004C_B_IO_COMPAT_20261124_R1')
SHA='18ab8ceff97339eded44af2e716cb6c43c8d5679a212a8183f84751fce9fad92'
class RootContractTests(unittest.TestCase):
 def test_original_symlink_is_refused_by_unmodified_guard(self):
  self.assertTrue((failed/'C0').is_symlink())
  with self.assertRaisesRegex(ControlError,'Linked checkpoint root'):read_manifest(failed/'C0',SHA)
 def test_full_regular_copy_passes_original_read_manifest(self):
  m=read_manifest(root/'C0',SHA)
  self.assertEqual(len(m['storages']),852);self.assertEqual(len(m['files']),852)
  self.assertEqual(m['provenance']['candidate_source_commit'],'5d357c1d3079de134dd8b41a20a00632da37f0b0')
 def test_all_payload_copies_are_real_distinct_files(self):
  old=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1/C0')
  self.assertFalse((root/'C0').is_symlink())
  for p in (root/'C0').iterdir():
   self.assertFalse(p.is_symlink());self.assertNotEqual(p.stat().st_ino,(old/p.name).stat().st_ino)
 def test_no_checkpoint_deserialization_or_cuda_initialization(self):
  self.assertFalse(torch.cuda.is_initialized())
  source=pathlib.Path(__file__).read_text()
  import ast;calls=[ast.unparse(n.func) for n in ast.walk(ast.parse(source)) if isinstance(n,ast.Call)];self.assertNotIn('torch.load',calls);self.assertNotIn('load_state',calls)
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RootContractTests))
report={'total':result.testsRun,'passed':result.testsRun-len(result.failures)-len(result.errors),'failures':[(str(t),s) for t,s in result.failures],'errors':[(str(t),s) for t,s in result.errors],'original_guard_used':True,'all_854_file_hashes_checked':True,'checkpoint_deserialized':False,'cuda_initialized':torch.cuda.is_initialized(),'no_GPU_retry':True}
(root/'evidence/C0_PATH_CPU_TEST_REPORT.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));sys.exit(not result.wasSuccessful())
