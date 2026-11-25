import unittest,pathlib,re,json,sys,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1'
raw=(ROOT/'02_candidate/task005b_r2_kernels.cu').read_bytes()
src=raw.decode('utf-8').replace('\r\n','\n')
def function(name):
 start=src.index('std::vector<torch::Tensor> '+name+'(')
 return src[start:src.index('\n}\n',start)+3]
class Contract(unittest.TestCase):
 def test_original_prefix_immutable(self):self.assertTrue(raw.startswith((OLD/'02_candidate/task005b_kernels.cu').read_bytes()))
 def test_remove_observations_restores_original_reference(self):
  f=function('ba_trace_reference_cuda')
  f=f.replace('ba_trace_reference_cuda(','ba_cuda(')
  f=re.sub(r'^.*// R2_OBSERVE .*\n','',f,flags=re.M)
  f=f.replace('  std::vector<torch::Tensor> trace;\n','')
  f=re.sub(r'^  TORCH_CHECK\(iterations == 2.*\n','',f,flags=re.M)
  f=f.replace('  std::vector<torch::Tensor> result{dx, dz};\n  result.insert(result.end(), trace.begin(), trace.end());\n  return result;','  return {dx, dz};')
  self.assertEqual(re.sub(r'\s+','',f),re.sub(r'\s+','',function('ba_cuda')))
 def test_internal_two_iteration_loop_preserved(self):
  for n in ['ba_trace_reference_cuda','ba_trace_paths_cuda']:self.assertIn('for (int itr=0; itr<iterations; itr++)',function(n))
 def test_linear_kernel_original(self):
  a=(OLD/'02_candidate/task005b_kernels.cu').read_text(encoding='utf-8')
  kernel=a[a.index('__global__ void linear_transform_kernel('):a.index('std::vector<torch::Tensor> ba_cuda(')]
  self.assertIn(kernel,src)
 def test_trace_schema_matches_emission_order(self):
  want=json.loads((ROOT/'02_candidate/TRACE_SCHEMA.json').read_text())
  for n in ['ba_trace_reference_cuda','ba_trace_paths_cuda']:self.assertEqual(re.findall(r'// R2_OBSERVE (\w+)',function(n)),want)
 def test_observation_has_no_write_to_original_tensor(self):
  for line in src.splitlines():
   if 'R2_OBSERVE' in line:self.assertRegex(line,r'trace\.push_back\(.+\.detach\(\)\.cpu\(\)\.clone\(\)\);')
 def test_no_atomic_replacement(self):
  f=function('ba_trace_reference_cuda');self.assertIn('linear_transform_kernel<<<kx.size(0), THREADS>>>',f)
 def test_no_clamp_or_parameter_change(self):
  for n in ['ba_trace_reference_cuda','ba_trace_paths_cuda']:
   f=function(n);self.assertNotIn('.clamp',f);self.assertIn('affine_weights += (du - weight_decay * affine_weights)',f)
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contract))
 out=ROOT/'03_tests/CPU_TEST_REPORT.json'
 out.write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'PASS':result.wasSuccessful()},indent=2)+'\n')
 raise SystemExit(0 if result.wasSuccessful() else 1)
