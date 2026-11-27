"""Independent mathematical checks and actual-cache integration assertions."""
from pathlib import Path
import csv,json,sys,unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import TASK,legacy,records,cpu_assert
from fusion_math import *
from sklearn.metrics import roc_auc_score,average_precision_score

class RiskMathematics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.original=legacy()
    def test_constant_rank_is_half(self):np.testing.assert_array_equal(percentile(np.ones((2,3))),np.full((2,3),.5))
    def test_average_ties_and_range(self):np.testing.assert_allclose(percentile([1,1,3,4]),[.25,.25,.625,.875])
    def test_rank_monotone_invariance(self):np.testing.assert_array_equal(percentile([3,1,2,2]),percentile([39,13,26,26]))
    def test_rank_rejects_nan(self):
        with self.assertRaises(ValueError):percentile([1,np.nan])
    def test_rank_rejects_empty(self):
        with self.assertRaises(ValueError):percentile([])
    def test_rank_entire_image_not_GT_selected(self):
        a=np.array([1,2,100,100]);full=percentile(a)
        self.assertFalse(np.array_equal(full[:2],percentile(a[:2])))
    def test_fusion_invariance_to_separate_positive_affine_transforms(self):
        c=np.array([[.1,.7],[2.,-1.]]);f=np.array([[.9,.3],[.1,.9]])
        a,_,_=scores(c,f);b,_,_=scores(c*20+8,f*9+11)
        for k in ['RankFusion','MaxFusion','RankW25','RankW75']:np.testing.assert_array_equal(a[k],b[k])
    def test_max_is_conservative_union(self):
        s,n,f=scores(np.array([.9,.7,.1]),np.array([.8,.3,.1]))
        np.testing.assert_array_equal(s['MaxFusion']>=.8,(n>=.8)|(f>=.8))
    def test_native_and_flip_directions(self):
        s,_,_=scores(np.array([3.,2.,1.]),np.array([0.,1.,2.]))
        self.assertTrue(np.all(np.diff(s['NativeOnly'])>0));self.assertTrue(np.all(np.diff(s['FlipOnly'])>0))
    def test_mismatched_grids_fail(self):
        with self.assertRaises(ValueError):scores(np.ones((2,2)),np.ones(4))
    def test_original_AUC_AP_against_independent_library(self):
        rng=np.random.default_rng(11);y=rng.integers(0,2,100);s=rng.integers(0,5,100)
        v=self.original.binary_ranking(y,s)
        self.assertAlmostEqual(v['AUROC'],roc_auc_score(y,s),14);self.assertAlmostEqual(v['AUPRC'],average_precision_score(y,s),14)
    def test_single_class_AUC_undefined(self):self.assertIsNone(self.original.binary_ranking(np.ones(4),np.arange(4))['AUROC'])
    def test_perfect_order_AUSE_zero(self):self.assertAlmostEqual(self.original.fast_rc(np.arange(1,6),np.arange(1,6))['AUSE'],0.,14)
    def test_constant_risk_equals_random(self):
        v=self.original.fast_rc(np.array([.8,.1,.4,.2]),np.ones(4));np.testing.assert_allclose(v['risk'],v['random'])
    def test_tie_permutation_does_not_improve_AUSE(self):
        e=np.array([.8,.1,.4,.2]);s=np.array([0,0,1,1]);ix=[1,0,3,2]
        self.assertAlmostEqual(self.original.fast_rc(e,s)['AUSE'],self.original.fast_rc(e[ix],s[ix])['AUSE'],14)
    def test_sequence_leakage_stops_logistic(self):
        with self.assertRaises(ValueError):fit_logistic(np.arange(4),[0,0,1,1],'0000','0000')
    def test_sequence_leakage_stops_regression(self):
        with self.assertRaises(ValueError):fit_regression(np.arange(4),[0,1,2,3],'0001','0001')
    def test_nonnegative_logistic_slope(self):
        m=fit_logistic(np.arange(8),[0,0,0,1,0,1,1,1]);self.assertGreaterEqual(m['slope'],0)
        p,_=logistic_predict(np.arange(8),m);self.assertTrue(np.all(np.diff(p)>=0))
    def test_reverse_event_cannot_silently_flip_risk(self):
        m=fit_logistic(np.arange(8),[1,1,1,1,0,0,0,0]);self.assertLess(m['slope'],1e-8)
    def test_logistic_invalid_event_rejected(self):
        with self.assertRaises(ValueError):fit_logistic(np.arange(4),[0,0,1,2])
    def test_probability_known_constant(self):
        m,_=probability_metrics(np.array([.5,.5]),np.zeros(2),[0,1]);self.assertAlmostEqual(m['Brier'],.25);self.assertAlmostEqual(m['NLL'],np.log(2));self.assertAlmostEqual(m['ECE10'],0)
    def test_extreme_logits_finite(self):
        m,_=probability_metrics(np.array([0.,1.]),np.array([-1000.,1000.]),[0,1]);self.assertTrue(np.isfinite(m['NLL']));self.assertEqual(m['Brier'],0)
    def test_invalid_probability_rejected(self):
        with self.assertRaises(ValueError):probability_metrics(np.array([-1.,1.]),np.zeros(2),[0,1])
    def test_regression_is_monotone_and_clipped(self):
        model,_=fit_regression(np.arange(6),[0,.3,.1,.8,.5,1.2]);p=model.predict([-100,0,1,2,3,4,5,100]);self.assertTrue(np.all(np.diff(p)>=0));self.assertEqual(p[0],p[1]);self.assertEqual(p[-1],p[-2])
    def test_negative_regression_error_rejected(self):
        with self.assertRaises(ValueError):fit_regression(np.arange(3),[0,-.1,1])

class ActualEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out=Path(json.loads((TASK/'private/LATEST_SUCCESSFUL_RUN.json').read_text())['path'])
    def read(self,name):
        with (self.out/name).open(encoding='utf-8') as f:return list(csv.DictReader(f))
    def test_48_historical_values_reproduced(self):
        rows=self.read('historical_reproduction.csv');self.assertEqual(len(rows),48);self.assertTrue(all(r['pass']=='True' for r in rows))
    def test_all_six_methods_and_views_present(self):
        rows=self.read('metrics_per_frame.csv');self.assertEqual(len(rows),72);self.assertEqual({r['method'] for r in rows},set(METHODS))
    def test_exact_old_scale_and_split(self):
        d=json.loads((self.out/'SCALES_AND_STATUS.json').read_text());self.assertAlmostEqual(d['scales']['FROZEN_BICUBIC_ZERO_EXTENDED'],15.985507037495662,12);self.assertFalse(d['fresh_independent_test'])
    def test_seven_zero_predictions_remain(self):
        rows=[r for r in self.read('depth_error_context.csv') if r['view']=='FROZEN_BICUBIC_ZERO_EXTENDED'];self.assertEqual(sum(int(r['zero_predictions_retained']) for r in rows),7)
    def test_all_models_fit_calibration_sequence_only(self):
        d=json.loads((self.out/'CALIBRATION_MODELS.json').read_text());self.assertEqual(len(d['models']),12)
        for r in d['models']:
            for k in ['probability','AbsRel_regression']:self.assertEqual(r[k]['calibration_sequence'],'0000');self.assertEqual(r[k]['evaluation_sequence'],'0001');self.assertFalse(r[k]['fit_on_evaluation'])
    def test_no_VIPER_accuracy_values(self):
        rows=self.read('viper_signal_statistics.csv');self.assertEqual(len(rows),80);self.assertTrue(all(r['dense_GT_available']=='False' for r in rows));self.assertFalse(any('AUROC' in r for r in rows))
    def test_all_16_rank_map_shapes_and_probability_scope(self):
        actual=records();self.assertEqual(len(actual),16)
        for r in actual:
            p=self.out/'risk_maps'/(r['sample']['sample_id']+'.npz')
            with np.load(p,allow_pickle=False) as z:
                for k in ['rank_native','rank_flip','risk_fusion','risk_max']:
                    self.assertEqual(list(z[k].shape),r['sample']['input_hw']);self.assertEqual(z[k].dtype,np.float64);self.assertTrue(np.isfinite(z[k]).all());self.assertTrue(((z[k]>=0)&(z[k]<=1)).all())
    def test_No_PyTorch_or_GPU(self):cpu_assert()

if __name__=='__main__':unittest.main(verbosity=2)
