"""All synthetic/oracle tests; never relabeled as Metric3D validation results."""
import io,itertools,json,pathlib,time,unittest
import numpy as np
from sklearn.metrics import roc_auc_score,average_precision_score
from reliability_metrics import *

GOOD=GTAdmission(True,True,True,True,'SYNTHETIC_FIXTURE','arbitrary_common_unit')

class TestAdmission(unittest.TestCase):
 def test_independent_GT_required(self):
  with self.assertRaises(AdmissionError):depth_errors([1],[1],[True],GTAdmission(False,True,True,True,'R1_geometry','unit'))
 def test_units_unknown_stops(self):
  with self.assertRaises(AdmissionError):depth_errors([1],[1],[True],GTAdmission(True,True,True,False,'MVS','UNKNOWN'))
 def test_alignment_unknown_stops(self):
  with self.assertRaises(AdmissionError):depth_errors([1],[1],[True],GTAdmission(True,False,True,True,'fixture','unit'))
 def test_depth_convention_unknown_stops(self):
  with self.assertRaises(AdmissionError):depth_errors([1],[1],[True],GTAdmission(True,True,False,True,'fixture','unit'))
 def test_invalid_GT_excluded_and_logged_by_mask(self):
  e,l,m=depth_errors([1,2,3,4],[1,np.inf,0,np.nan],[1,1,1,1],GOOD)
  np.testing.assert_array_equal(m,[1,0,0,0]);np.testing.assert_array_equal(e,[0]);np.testing.assert_array_equal(l,[0])
 def test_invalid_pred_not_silently_dropped(self):
  with self.assertRaises(AdmissionError):depth_errors([1,np.nan],[1,2],[1,1],GOOD)
 def test_no_valid_GT_stops(self):
  with self.assertRaises(AdmissionError):depth_errors([1],[np.inf],[1],GOOD)
 def test_raw_relative_and_log_error(self):
  e,l,m=depth_errors([2,1],[1,2],[1,1],GOOD,epsilon=0)
  np.testing.assert_array_equal(e,[1,.5]);np.testing.assert_allclose(l,np.log(2))
 def test_shape_mismatch_stops(self):
  with self.assertRaises(ValueError):depth_errors([1,2],[1],[1],GOOD)

class TestRanking(unittest.TestCase):
 def test_perfect_binary(self):
  r=binary_ranking([0,0,1,1],[0,1,2,3]);self.assertEqual(r['AUROC'],1);self.assertEqual(r['AUPRC'],1)
 def test_reversed_binary(self):self.assertEqual(binary_ranking([0,0,1,1],[3,2,1,0])['AUROC'],0)
 def test_all_ties_are_random_not_input_order(self):
  r=binary_ranking([0,0,1,1],[1,1,1,1]);self.assertEqual(r['AUROC'],.5);self.assertEqual(r['AUPRC'],.5)
 def test_single_class_metrics_undefined(self):
  for labels in ([0,0],[1,1]):
   r=binary_ranking(labels,[1,2]);self.assertIsNone(r['AUROC']);self.assertIsNone(r['AUPRC'])
 def test_confidence_direction_is_explicit(self):
  r=evaluate_signal([.01,.1,.3,.9],[.9,.8,.6,.1],'higher_is_confidence')
  self.assertLess(r['error_vs_raw']['Spearman'],0);self.assertGreater(r['error_vs_declared_risk']['Spearman'],0)
 def test_wrong_direction_not_automatically_fixed(self):
  r=evaluate_signal([.01,.1,.3,.9],[.01,.1,.3,.9],'higher_is_confidence')
  self.assertGreater(r['error_vs_raw']['Spearman'],0);self.assertEqual(r['thresholds']['0.2']['AUROC'],0)
 def test_multiple_error_thresholds_retained(self):
  r=evaluate_signal([.1,.3,.6],[.1,.3,.6]);self.assertEqual(set(r['thresholds']),{'0.1','0.2','0.5'})
 def test_constant_correlation_not_zero_imputed(self):
  self.assertIsNone(correlation([1,2],[0,0])['Spearman'])
 def test_NaN_score_rejected(self):
  with self.assertRaises(ValueError):binary_ranking([0,1],[0,np.nan])

def ranking_case(seed):
 def test(self):
  rng=np.random.default_rng(seed);n=201
  y=rng.integers(0,2,n);s=rng.integers(0,11,n).astype(float)
  r=binary_ranking(y,s)
  self.assertAlmostEqual(r['AUROC'],roc_auc_score(y,s),places=14)
  self.assertAlmostEqual(r['AUPRC'],average_precision_score(y,s),places=14)
 return test
for seed in (0,1,2,3,7,43,44,45,1729,20261126):setattr(TestRanking,f'test_sklearn_oracle_seed_{seed}',ranking_case(seed))

class TestRiskCoverage(unittest.TestCase):
 def test_oracle_AUSE_zero(self):self.assertAlmostEqual(risk_coverage([1,2,3],[1,2,3])['AUSE_raw_AbsRel'],0)
 def test_constant_score_AURG_zero(self):self.assertAlmostEqual(risk_coverage([1,2,3],[1,1,1])['AURG_raw_AbsRel'],0)
 def test_bad_ranking_negative_AURG(self):self.assertLess(risk_coverage([1,2,3],[3,2,1])['AURG_raw_AbsRel'],0)
 def test_tie_expected_prefix_matches_enumeration(self):
  e=np.array([1.,4.,2.,8.]);r=risk_coverage(e,np.ones(4))
  curves=[np.cumsum(e[list(order)])/np.arange(1,5) for order in itertools.permutations(range(4))]
  np.testing.assert_allclose(r['risk'][1:],np.mean(curves,axis=0),atol=1e-14,rtol=0)
 def test_tie_permutation_invariance(self):
  a=risk_coverage([1,9,4,2],[0,0,1,1]);b=risk_coverage([9,1,2,4],[0,0,1,1])
  np.testing.assert_array_equal(a['risk'],b['risk'])
 def test_zero_error_returns_zero_areas(self):
  r=risk_coverage([0,0,0],[2,1,3]);self.assertEqual(r['AUSE_raw_AbsRel'],0);self.assertEqual(r['AURG_raw_AbsRel'],0)
 def test_negative_error_rejected(self):
  with self.assertRaises(ValueError):risk_coverage([-1,2],[1,2])

class TestCalibration(unittest.TestCase):
 def test_raw_confidence_not_ECE(self):self.assertIsNone(evaluate_signal([1,2],[0,1])['calibration_ECE'])
 def test_bins_are_not_probability_claim(self):
  self.assertFalse(reliability_bins([1,2,3],[2,5,9],2)[0]['is_probability_calibration'])
 def test_sequence_leakage_stops(self):
  with self.assertRaises(AdmissionError):probability_calibration([.1,.9],[0,1],fitted_on_sequences=['a'],test_sequences=['a'],event_definition='e>0.2')
 def test_missing_calibration_stops(self):
  with self.assertRaises(AdmissionError):probability_calibration([.1],[0],fitted_on_sequences=[],test_sequences=['b'],event_definition='e>0.2')
 def test_probability_bounds_checked(self):
  with self.assertRaises(ValueError):probability_calibration([-1],[0],fitted_on_sequences=['a'],test_sequences=['b'],event_definition='e>0.2')
 def test_perfect_event_probabilities_zero_ECE(self):
  r=probability_calibration([0.,1.],[0,1],fitted_on_sequences=['a'],test_sequences=['b'],event_definition='e>0.2');self.assertEqual(r['ECE'],0)
 def test_probability_one_not_lost(self):
  r=probability_calibration([.2,1.],[0,1],fitted_on_sequences=['a'],test_sequences=['b'],event_definition='e>0.2');self.assertEqual(sum(x['n'] for x in r['bins']),2)

class TestTTA(unittest.TestCase):
 def test_correct_inverse_flip(self):
  a=np.array([[1.,2.,3.],[4.,5.,6.]]);u,l=flip_disagreement(a,a[:,::-1]);np.testing.assert_array_equal(u,np.zeros_like(a))
 def test_consistently_wrong_model_is_not_detected(self):
  a=np.full((2,3),100.);u,_=flip_disagreement(a,a);self.assertEqual(u.max(),0)
  self.assertGreater(np.mean(np.abs(a-1)),90)
 def test_TTA_relative_and_log_scores(self):
  a=np.array([[1.,2.]]);b=np.array([[4.,2.]]);u,l=flip_disagreement(a,b)
  np.testing.assert_allclose(u,[[(2-1)/(1+1e-6),(4-2)/(2+1e-6)]])
 def test_invalid_TTA_depth_stops(self):
  with self.assertRaises(AdmissionError):flip_disagreement([[0,1]],[[1,1]])
 def test_resize_padding_native_dimensions(self):
  g=preprocess_geometry(360,640);self.assertEqual(g['scaled_hw'],[598,1064]);self.assertEqual(g['pad_tblr'],[9,9,0,0])
 def test_zero_bottom_padding_does_not_empty_map(self):
  a=np.arange(12).reshape(3,4);np.testing.assert_array_equal(unpad_grid(a,[0,0,0,0]),a)
 def test_odd_padding(self):
  a=np.arange(48).reshape(6,8);self.assertEqual(unpad_grid(a,[1,2,0,1]).shape,(3,7))

class TestDepthBins(unittest.TestCase):
 def test_uniform_entropy_and_variance(self):
  s=depth_bin_statistics(np.zeros((4,2)),[1,2,3,4]);np.testing.assert_allclose(s['entropy_normalized'],1);np.testing.assert_allclose(s['variance'],1.25)
  np.testing.assert_allclose(s['effective_bins'],4)
 def test_one_hot_limit(self):
  s=depth_bin_statistics(np.array([[1000.],[0.],[-1000.]]),[1,2,3]);self.assertAlmostEqual(s['max_probability'][0],1);self.assertAlmostEqual(s['variance'][0],0)
 def test_logit_shift_invariance(self):
  a=np.array([[1.,4.],[3.,1.],[2.,5.]]);np.testing.assert_allclose(entropy_from_logits(a),entropy_from_logits(a+1000),rtol=1e-13,atol=1e-13)
 def test_actual_anchor_count_required(self):
  with self.assertRaises(ValueError):depth_bin_statistics(np.zeros((4,2)),[1,2,3])
 def test_initial_distribution_does_not_determine_final_error(self):
  s=depth_bin_statistics(np.zeros((4,1)),[1,2,3,4]);self.assertAlmostEqual(s['mean_initial_depth'][0],2.5)
  # A later refinement may yield either 2.5 or 100, with the same initial entropy.
  self.assertNotEqual(abs(2.5-2.5),abs(100-2.5))

class TestTrainingMask(unittest.TestCase):
 def test_gross_errors_not_confidence_supervised(self):
  loss,target,mask=supervised_confidence_loss([.1,.2,.3],[1.,2.,3.],[1.,1.,1.],[1,1,1]);np.testing.assert_array_equal(mask,[1,0,0])
 def test_wrong_pixel_confidence_unconstrained_by_this_loss(self):
  a=supervised_confidence_loss([.1,-100],[1,5],[1,1],[1,1])[0]
  b=supervised_confidence_loss([.1,100],[1,5],[1,1],[1,1])[0];self.assertEqual(a,b)
 def test_correct_target_confidence(self):
  _,t,m=supervised_confidence_loss([.9,.5],[1.1,.5],[1.,1.],[1,1]);np.testing.assert_allclose(t,[.9,.5])

class TestGroupedStatistics(unittest.TestCase):
 def test_one_sequence_has_no_cross_sequence_interval(self):
  r=grouped_bootstrap([1,2,3],['0000']*3);self.assertIsNone(r['lower95']);self.assertEqual(r['groups'],1)
 def test_group_macro_prevents_long_sequence_dominance(self):
  r=grouped_bootstrap([0]*100+[10],['a']*100+['b']);self.assertEqual(r['mean'],5)
 def test_group_resampling_reproducibility(self):
  a=grouped_bootstrap([1,2,5],['a','b','c'],seed=43);b=grouped_bootstrap([1,2,5],['a','b','c'],seed=43);self.assertEqual(a,b)
 def test_constant_group_interval(self):
  r=grouped_bootstrap([2,2,2],['a','b','c']);self.assertEqual(r['lower95'],2);self.assertEqual(r['upper95'],2)

class Recording(unittest.TextTestResult):
 def __init__(self,*a,**k):super().__init__(*a,**k);self.records=[]
 def startTest(self,t):super().startTest(t);self.start=time.perf_counter();self.state='PASS';self.detail=None
 def addError(self,t,e):self.state='ERROR';self.detail=self._exc_info_to_string(e,t);super().addError(t,e)
 def addFailure(self,t,e):self.state='FAIL';self.detail=self._exc_info_to_string(e,t);super().addFailure(t,e)
 def stopTest(self,t):self.records.append({'test':t.id(),'status':self.state,'seconds':time.perf_counter()-self.start,'detail':self.detail});super().stopTest(t)

def run(out):
 out.mkdir(exist_ok=False)
 buf=io.StringIO();r=unittest.TextTestRunner(stream=buf,verbosity=2,resultclass=Recording).run(unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__)))
 (out/'stdout.txt').write_text(buf.getvalue(),encoding='utf-8')
 d={'tests':r.testsRun,'passed':sum(x['status']=='PASS' for x in r.records),'success':r.wasSuccessful(),'records':r.records,
    'scope':'Synthetic evaluator and source-mask contract tests; NOT Metric3D inference or confidence accuracy evidence'}
 (out/'CPU_TEST_REPORT.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8');return d

if __name__=='__main__':unittest.main()
