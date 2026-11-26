"""Mathematical and real-output contracts for the isolated depth evaluator."""
import ast,json,pathlib,sys,unittest
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'code'))
from common import *
from depth_restoration import *

def row(shape=(3,5),target=(7,9)):
    return {'padding_ltrb':[0,0,0,0],'canonical_hw':list(shape),'resized_hw':list(shape),'resize_scale':1.2,
      'sample':{'input_hw':list(target),'source_hw':list(target),'fx':600.,'source_fx':600.}}

class MathContracts(unittest.TestCase):
    def test_constant_field(self):
        self.assertTrue(np.allclose(resize_bilinear(np.full((3,5),7.),(8,11)),7.))
    def test_identity_grid(self):
        a=np.arange(35.).reshape(5,7);np.testing.assert_array_equal(resize_bilinear(a,a.shape),a)
    def test_singleton_both_axes(self):
        np.testing.assert_array_equal(resize_bilinear(np.array([[8.]]),(7,13)),np.full((7,13),8.))
    def test_singleton_height(self):
        out=resize_bilinear(np.array([[1.,2.,3.]]),(5,9));np.testing.assert_allclose(out[0],out[-1])
    def test_singleton_width(self):
        out=resize_bilinear(np.array([[1.],[2.],[3.]]),(9,5));np.testing.assert_allclose(out[:,0],out[:,-1])
    def test_positive_convex_hull(self):
        a=np.array([[.1,1000.],[1000.,.1]])
        for f in [resize_bilinear,resize_bilinear_float32]:
            p=f(a,(17,19));self.assertGreaterEqual(p.min(),.1-1e-7);self.assertLessEqual(p.max(),1000.+1e-6)
    def test_step_stays_positive(self):
        a=np.array([[.1,.1,100.,100.]]);self.assertGreater(resize_bilinear(a,(3,31)).min(),0.)
    def test_pixel_center_linear_ramp_interior(self):
        a=np.tile(np.arange(5.),(3,1));p=resize_bilinear(a,(6,10))
        np.testing.assert_allclose(p[2,1:-1],(np.arange(1,9)+.5)*.5-.5)
    def test_resize_roundtrip_not_assumed_identity(self):
        a=np.eye(4);self.assertFalse(np.allclose(resize_bilinear(resize_bilinear(a,(3,3)),(4,4)),a))
    def test_invalid_network_nan_refused(self):
        with self.assertRaises(ValueError):restore_positive_depth(np.full((3,5),np.nan),row())
    def test_invalid_network_inf_refused(self):
        with self.assertRaises(ValueError):restore_positive_depth(np.full((3,5),np.inf),row())
    def test_network_zero_not_epsilon_filled(self):
        a=np.ones((3,5));a[0,0]=0.
        with self.assertRaises(ValueError):restore_positive_depth(a,row())
    def test_network_negative_not_clamped_into_validity(self):
        a=np.ones((3,5));a[0,0]=-1.
        with self.assertRaises(ValueError):restore_positive_depth(a,row())
    def test_nonpositive_focal_refused(self):
        r=row();r['sample']['fx']=0.
        with self.assertRaises(ValueError):restore_positive_depth(np.ones((3,5)),r)
    def test_canonical_shape_refused(self):
        with self.assertRaises(ValueError):restore_positive_depth(np.ones((4,5)),row())
    def test_padding_receipt_refused(self):
        r=row();r['padding_ltrb']=[0,1,0,0]
        with self.assertRaises(ValueError):restore_positive_depth(np.ones((3,5)),r)
    def test_odd_padding(self):
        r=row((6,9),(7,11));r['padding_ltrb']=[1,1,2,2];r['resized_hw']=[3,6]
        a=np.full((6,9),100.);a[1:4,1:7]=2.
        np.testing.assert_allclose(restore_positive_depth(a,r,arithmetic='float64'),1.2)
    def test_focal_variant_ratio(self):
        r=row();a=np.full((3,5),2.)
        x=restore_positive_depth(a,r,arithmetic='float64');y=restore_positive_depth(a,r,arithmetic='float64',focal_convention='official_resized')
        np.testing.assert_allclose(y/x,1.2)
    def test_image_upsize_does_not_change_depth_unit(self):
        r=row();r['sample']['source_hw']=[14,18]
        p=restore_positive_depth(np.full((3,5),10.),r,output_grid='source',arithmetic='float64')
        self.assertEqual(p.shape,(14,18));np.testing.assert_allclose(p,6.)
    def test_unknown_mode_refused(self):
        with self.assertRaises(ValueError):restore_positive_depth(np.ones((3,5)),row(),focal_convention='tuned')
    def test_cap_must_be_positive(self):
        with self.assertRaises(ValueError):restore_positive_depth(np.ones((3,5)),row(),cap=0.)
    def test_native_cap_kept(self):
        p=restore_positive_depth(np.full((3,5),1000.),row());np.testing.assert_allclose(p,300.)
    def test_K_transform_roundtrip(self):
        k=np.array([[579.,0,480.],[0,578.,270.],[0,0,1.]])
        c=intrinsics_chain(k,[540,960],[540,960],[598,1064],[0,9,0,9])
        np.testing.assert_allclose(c['K_roundtrip'],k,rtol=1e-14,atol=1e-12)
    def test_K_projection_equivariance(self):
        k=np.array([[579.,0,480.],[0,578.,270.],[0,0,1.]])
        c=intrinsics_chain(k,[1080,1920],[360,640],[598,1064],[0,9,0,9]);xyz=np.array([.3,.2,2.])
        p=k@xyz;p/=p[2];a=c['source_to_canonical']@p;b=c['K_canonical']@xyz;b/=b[2]
        np.testing.assert_allclose(a,b,atol=1e-12)
    def test_half_pixel_is_not_corner_scaling(self):
        m=pixel_center_resize_matrix(1/3,1/3);self.assertAlmostEqual(m[0,2],-1/3)
    def test_physical_unit_gauge_cannot_be_identified(self):
        k=np.array([[500.,0,100.],[0,500.,100.],[0,0,1.]])
        xyz=np.array([1.,2.,8.]);t=np.array([.2,.1,.7]);a=k@(xyz+t);b=k@(10*xyz+10*t)
        np.testing.assert_allclose(a/a[2],b/b[2])
    def test_error_classes_do_not_drop_zero_prediction(self):
        gt=np.array([2.,2.,2.]);p=np.array([0.,2.,4.]);e=abs(p-gt)/gt
        self.assertEqual(int((e>=1).sum()),2);self.assertEqual(float(e[0]),1.)
    def test_confidence_score_not_probability(self):
        r=json.loads((ROOT/'PROTOCOL.json').read_text());self.assertIn('no P(error)',r['native_confidence'])
    def test_no_new_test_or_probability_fit_claim(self):
        r=json.loads((ROOT/'04_evaluation/EVALUATION_STATUS.json').read_text());self.assertEqual(r['new_probability_models'],0)
        self.assertIn('PREVIOUSLY_OBSERVED',r['test0001'])
    def test_GT_all_valid_pixels_preserved(self):
        import csv
        r=list(csv.DictReader((ROOT/'04_evaluation/PAIRED_DEPTH_ERROR_METRICS.csv').open()))
        for sid in {x['sample_id'] for x in r}:self.assertEqual(len({x['GT_valid_pixels'] for x in r if x['sample_id']==sid}),1)
    def test_old_seven_zero_positions_repaired(self):
        import csv
        r=list(csv.DictReader((ROOT/'04_evaluation/ORIGINAL_SEVEN_ZERO_PIXELS.csv').open()))
        self.assertEqual(len(r),7);self.assertTrue(all(float(x['bilinear_same_focal_depth'])>0 for x in r))
    def test_no_old_arrays_overwritten(self):
        old=json.loads((ROOT/'00_evidence/PRESERVATION_BEFORE.json').read_text())
        for r in old['files']:
            if r['kind']=='SEALED_R2_1_PAYLOAD':self.assertEqual(sha(r['path']),r['sha256'])
    def test_remote_CPU_runner_no_models_or_GPU_calls(self):
        tree=ast.parse((ROOT/'code/remote_cpu_restore.py').read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                name=ast.unparse(node.func)
                self.assertNotIn(name,['torch.load','torch.hub.load','model.inference','torch.cuda.init'])
                self.assertFalse(name.startswith('torch.cuda.'))

class NativeCPUFixtures(unittest.TestCase):pass
fixtures=json.loads((ROOT/'02_restoration/torch_CPU/CPU_RESTORE_RECEIPT.json').read_text('utf-8'))['fixtures']
for item in fixtures:
    def test(self,item=item):
        with np.load(ROOT/'02_restoration/torch_CPU/CPU_INTERPOLATION_FIXTURES.npz',allow_pickle=False) as a:
            mine=resize_bilinear_float32(a[f"input_{item['id']}"],item['output_shape'])
            np.testing.assert_allclose(mine,a[f"output_{item['id']}"],rtol=2e-5,atol=2e-5)
    setattr(NativeCPUFixtures,f"test_native_CPU_fixture_{item['id']}",test)

class RealMaps(unittest.TestCase):pass
for r in records():
    for mode in ['native','flip']:
        def test(self,r=r,mode=mode):
            sid=r['sample']['sample_id']
            with np.load(r['local_npz'],allow_pickle=False) as a,np.load(ROOT/'02_restoration/torch_CPU'/(sid+'.npz'),allow_pickle=False) as b:
                mine=restore_positive_depth(a[mode+'_canonical_depth'],r)
                np.testing.assert_allclose(mine,b[mode+'_bilinear_same_focal'],rtol=3e-5,atol=3e-4)
                self.assertTrue(np.isfinite(mine).all());self.assertTrue((mine>0).all())
        setattr(RealMaps,'test_'+r['sample']['sample_id']+'_'+mode,test)
