"""Independent regression oracles for fast risk integration and spatial sampling."""
import io,json,pathlib,time,unittest
import numpy as np
from evaluate_pilot import fast_rc,resize_linear,restore_bin,zero_extended_depth_errors,ROOT
from reliability_metrics import risk_coverage,GTAdmission,depth_errors,AdmissionError
from test_reliability import Recording

class TestEvaluationGeometry(unittest.TestCase):
 def test_fast_curve_matches_reference_with_ties(self):
  for seed in range(20):
   rng=np.random.default_rng(seed);e=rng.uniform(0,5,60);s=rng.integers(0,5,60)
   slow=risk_coverage(e,s);fast=fast_rc(e,s)
   for key in ['risk','oracle','random','coverage']:np.testing.assert_allclose(slow[key],fast[key],atol=1e-14,rtol=1e-14)
   self.assertAlmostEqual(slow['AUSE_raw_AbsRel'],fast['AUSE'],places=13)
 def test_fast_curve_unique_scores(self):
  rng=np.random.default_rng(43);e=rng.random(200);s=rng.random(200)
  np.testing.assert_allclose(fast_rc(e,s)['risk'],risk_coverage(e,s)['risk'],atol=1e-14)
 def test_constant_signal_is_random(self):
  r=fast_rc([.1,.4,9,1.2],[1,1,1,1]);np.testing.assert_allclose(r['risk'],r['random']);self.assertAlmostEqual(r['AURG'],0)
 def test_invalid_signal_stops(self):
  for e,s in [([],[]),([1],[np.nan]),([-1],[0]),([1],[np.inf]),([1,2],[0])]:
   with self.assertRaises(ValueError):fast_rc(e,s)
 def test_pixel_center_bilinear_grid_oracle(self):
  a=np.array([[0,1],[2,3.]])
  expected=np.array([[0,.25,.75,1],[.5,.75,1.25,1.5],[1.5,1.75,2.25,2.5],[2,2.25,2.75,3]])
  np.testing.assert_allclose(resize_linear(a,(4,4)),expected,atol=1e-14)
 def test_restore_same_constant_grid_with_odd_padding(self):
  row={'padding_ltrb':[0,8,0,9],'sample':{'input_hw':[540,960]}}
  z=restore_bin(np.full((154,266),3.4),row);self.assertEqual(z.shape,(540,960));np.testing.assert_allclose(z,3.4)
 def test_real_unconstrained_confidence_kept_raw(self):
  path=ROOT/'01_smoke/smoke_qualified/VIPER_Night_val007_00001.npz'
  with np.load(path,allow_pickle=False) as a:
   c=a['native_confidence'];self.assertLess(c.min(),0);self.assertGreater(c.max(),1);self.assertTrue(np.isfinite(c).all())
 def test_real_readonly_hook_bitwise_equality(self):
  d=json.loads((ROOT/'01_smoke/smoke_qualified/HOOK_EQUIVALENCE.json').read_text())
  self.assertEqual(d['depth_max_abs_diff'],0);self.assertEqual(d['confidence_max_abs_diff'],0)
 def test_zero_prediction_stays_error_one_and_log_infinite(self):
  admission=GTAdmission(True,True,True,True,'synthetic oracle','native_numeric')
  e,l,m=zero_extended_depth_errors([0,2],[2,2],[1,1],admission)
  np.testing.assert_allclose(e,[1,0],atol=1e-12);self.assertTrue(np.isinf(l[0]));self.assertEqual(len(e),2)
 def test_negative_prediction_not_accepted_by_extension(self):
  admission=GTAdmission(True,True,True,True,'synthetic oracle','native_numeric')
  with self.assertRaises(ValueError):zero_extended_depth_errors([-1],[2],[1],admission)
 def test_original_strict_gate_still_rejects_zero(self):
  admission=GTAdmission(True,True,True,True,'synthetic oracle','native_numeric')
  with self.assertRaises(AdmissionError):depth_errors([0],[2],[1],admission)
 def test_zero_TTA_formula_has_finite_large_disagreement(self):
  a=np.array([0.,2]);b=np.array([2.,2]);relative=np.abs(a-b)/(np.abs(a)+1e-6)
  self.assertEqual(relative[0],2e6);self.assertEqual(relative[1],0)
 def test_real_7_zero_predictions_preserved(self):
  path=ROOT/'02_pilot/pilot/MVS_0001_0099.npz'
  with np.load(path,allow_pickle=False) as a:
   zeros=a['native_depth']==0
   self.assertGreaterEqual(zeros.sum(),7);self.assertTrue((a['native_depth_unclipped'][zeros]<0).all())
   self.assertGreater(a['native_canonical_depth'].min(),0)

if __name__=='__main__':
 out=ROOT/'experiments/cpu_tests_003';out.mkdir(exist_ok=False)
 buf=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromTestCase(TestEvaluationGeometry)
 result=unittest.TextTestRunner(stream=buf,verbosity=2,resultclass=Recording).run(suite)
 (out/'stdout.txt').write_text(buf.getvalue(),encoding='utf-8')
 data={'tests':result.testsRun,'passed':sum(x['status']=='PASS' for x in result.records),'success':result.wasSuccessful(),'records':result.records,
       'scope':'CPU evaluator/grid oracles plus real-output readback assertions, no new model inference'}
 (out/'CPU_TEST_REPORT.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in data.items() if k!='records'}))
 if not result.wasSuccessful():raise SystemExit(1)
