"""Meaningful CPU checks. These do not certify CUDA or actual SLAM results."""
import os,sys,pathlib,json,unittest,hashlib,time
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'03_candidate'))
from depth_paths import regularization,solve,contrasts,spectrum
from generate_native_candidate import SOURCE,EXPECTED_BLOB,build,TRACE_NAMES

def fixture(seed=105):
    rng=np.random.default_rng(seed)
    # Separate depth columns: native depth block is diagonal.
    Jx=rng.normal(size=(20,3));Jz=np.zeros((20,5))
    for i in range(20):Jz[i,i%5]=rng.normal()
    residual=rng.normal(size=20)
    return dict(A=Jx.T@Jx,E=Jx.T@Jz,v=Jx.T@residual,cg=np.diag(Jz.T@Jz).copy(),wg=Jz.T@residual,
                d=np.array([.5,.7,1,1.2,.3]),dm=np.array([.4,0,.8,-1,.45]),eta=np.arange(1,6)*1e-7,alpha=.01)

class MathematicalTests(unittest.TestCase):
    def test_A_equals_original_D1(self):
        z=fixture();m=(z['dm']>0);c,w,_=regularization(z['cg'],z['wg'],z['d'],z['dm'],z['eta'],z['alpha'],1,1)
        np.testing.assert_array_equal(c,z['cg']+m*.01+(1-m)*z['eta'])
        np.testing.assert_array_equal(w,z['wg']-m*.01*(z['d']-z['dm']))
    def test_D_equals_original_zero_prior(self):
        z=fixture();c,w,_=regularization(z['cg'],z['wg'],z['d'],z['dm'],z['eta'],.01,0,0)
        np.testing.assert_array_equal(c,z['cg']+z['eta']);np.testing.assert_array_equal(w,z['wg'])
    def test_B_changes_only_curvature(self):
        z=fixture();a=solve(**z,c=1,g=0);d=solve(**z,c=0,g=0)
        np.testing.assert_array_equal(a['w'],d['w']);self.assertGreater(np.linalg.norm(a['C']-d['C']),0)
    def test_C_changes_only_gradient(self):
        z=fixture();a=solve(**z,c=0,g=1);d=solve(**z,c=0,g=0)
        np.testing.assert_array_equal(a['C'],d['C']);self.assertGreater(np.linalg.norm(a['w']-d['w']),0)
    def test_missing_prior_invariant(self):
        z=fixture();s=[solve(**z,c=c,g=g) for c,g in ((1,1),(1,0),(0,1),(0,0))]
        for a in s:
            np.testing.assert_array_equal(a['C'][[1,3]],z['cg'][[1,3]]+z['eta'][[1,3]])
            np.testing.assert_array_equal(a['w'][[1,3]],z['wg'][[1,3]])
    def test_zero_prior_all_cells_identical(self):
        z=fixture();z['dm']*=0;base=solve(**z,c=0,g=0)
        for c,g in ((1,1),(1,0),(0,1)):
            a=solve(**z,c=c,g=g);np.testing.assert_array_equal(a['dx'],base['dx'])
    def test_schur_matches_full_joint_normal_equations(self):
        z=fixture()
        for c,g in ((1,1),(1,0),(0,1),(0,0)):
            a=solve(**z,c=c,g=g);joint=np.block([[z['A']+np.diag(.1+1e-4*np.diag(a['H'])),z['E']],[z['E'].T,np.diag(a['C'])]])
            direct=np.linalg.solve(joint,np.r_[z['v'],a['w']]);np.testing.assert_allclose(direct,np.r_[a['dx'],a['dz']],atol=1e-12,rtol=1e-12)
    def test_native_damping_uses_schur_diagonal(self):
        z=fixture();a=solve(**z,c=0,g=0)
        np.testing.assert_allclose(a['L']-a['H'],np.diag(.1+1e-4*np.diag(a['H'])),atol=1e-15)
        self.assertGreater(np.linalg.norm(np.diag(a['H'])-np.diag(z['A'])),.1)
    def test_prior_force_sign_and_analytic_effect(self):
        z=fixture()
        for c in (0,1):
            on=solve(**z,c=c,g=1);off=solve(**z,c=c,g=0)
            predicted=np.linalg.solve(on['L'],z['E']@(on['Q']*on['p']))
            np.testing.assert_allclose(on['dx']-off['dx'],predicted,atol=1e-15)
    def test_gradient_does_not_change_first_linearized_spectrum(self):
        z=fixture()
        for c in (0,1):np.testing.assert_array_equal(solve(**z,c=c,g=1)['L'],solve(**z,c=c,g=0)['L'])
    def test_two_path_effect_is_not_additive(self):
        z=fixture();z['alpha']=2
        vals={n:solve(**z,c=c,g=g)['dx'] for n,(c,g) in zip('ABCD',((1,1),(1,0),(0,1),(0,0)))}
        self.assertGreater(np.linalg.norm(contrasts(vals)['interaction']),1e-6)
    def test_contrast_closure(self):
        z=fixture();vals={n:solve(**z,c=c,g=g)['dx'] for n,(c,g) in zip('ABCD',((1,1),(1,0),(0,1),(0,0)))}
        e=contrasts(vals)
        np.testing.assert_allclose(e['curvature_at_g0']+e['gradient_at_c0']+e['interaction'],e['total_on_minus_off'],atol=1e-15)
        np.testing.assert_allclose(e['curvature_average']+e['gradient_average'],e['total_on_minus_off'],atol=1e-15)
    def test_zero_prior_error_removes_gradient(self):
        z=fixture();z['dm']=z['d'].copy()
        for c in (0,1):np.testing.assert_array_equal(solve(**z,c=c,g=0)['dx'],solve(**z,c=c,g=1)['dx'])
    def test_no_pose_depth_coupling_no_pose_effect(self):
        z=fixture();z['E']*=0;base=solve(**z,c=0,g=0)
        for c,g in ((1,1),(1,0),(0,1)):np.testing.assert_array_equal(base['dx'],solve(**z,c=c,g=g)['dx'])
    def test_alpha_equal_eta_removes_curvature_effect(self):
        z=fixture();z['eta']=np.ones(5)*z['alpha']
        for g in (0,1):np.testing.assert_array_equal(solve(**z,c=0,g=g)['dx'],solve(**z,c=1,g=g)['dx'])
    def test_zero_alpha_does_not_in_general_equal_D0(self):
        z=fixture();z['alpha']=0;z['eta']*=1e7
        self.assertGreater(np.linalg.norm(solve(**z,c=1,g=1)['dx']-solve(**z,c=0,g=0)['dx']),1e-6)
    def test_masks_do_not_silently_accept_nan(self):
        z=fixture();z['dm'][0]=np.nan
        with self.assertRaises(ValueError):solve(**z,c=1,g=1)
    def test_inf_rejected(self):
        z=fixture();z['eta'][0]=np.inf
        with self.assertRaises(ValueError):solve(**z,c=1,g=1)
    def test_zero_depth_block_rejected(self):
        z=fixture();z['cg']*=0;z['eta']*=0
        with self.assertRaises(ValueError):solve(**z,c=0,g=0)
    def test_shapes_rejected(self):
        z=fixture();z['dm']=z['dm'][:2]
        with self.assertRaises(ValueError):solve(**z,c=0,g=0)
    def test_invalid_factor_rejected(self):
        with self.assertRaises(ValueError):solve(**fixture(),c=2,g=0)
    def test_rank_deficiency_no_fake_finite_condition_number(self):
        s=spectrum(np.diag([1.,0.]));self.assertEqual(s['rank'],1);self.assertIsNone(s['kappa2']);self.assertFalse(s['SPD'])
    def test_indefinite_matrix_not_classified_as_SPD(self):
        s=spectrum(np.diag([-1.,2.]));self.assertFalse(s['SPD']);self.assertEqual(s['kappa2'],2.)
    def test_native_lower_triangle_not_averaged(self):
        a=np.array([[2.,.7],[.3,1.]])
        s=spectrum(a);np.testing.assert_array_equal(s['effective_matrix'],[[2,.3],[.3,1]])
        self.assertGreater(s['asymmetry_fro'],0)
    def test_input_arrays_unchanged(self):
        z=fixture();before={k:v.copy() for k,v in z.items() if isinstance(v,np.ndarray)}
        solve(**z,c=1,g=1)
        for k,v in before.items():np.testing.assert_array_equal(z[k],v)

class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=SOURCE.read_bytes();cls.cu,cls.cpp,cls.original,cls.entry=build(cls.raw)
    def test_original_file_git_blob(self):
        self.assertEqual(hashlib.sha1(b'blob '+str(len(self.raw)).encode()+b'\0'+self.raw).hexdigest(),EXPECTED_BLOB)
    def test_original_all_functions_preserved_byte_identical(self):self.assertTrue(self.cu.encode().startswith(self.raw))
    def test_candidate_in_separate_entry(self):
        self.assertEqual(self.cu.count('std::vector<torch::Tensor> ba_paths_cuda('),1)
        self.assertEqual(self.cu.count('std::vector<torch::Tensor> ba_cuda('),1)
    def test_geometry_kernel_call_unchanged(self):
        a=self.original.split('    projective_transform_kernel<<<')[1].split('enable_bidirectional_uncer);')[0]
        b=self.entry.split('    projective_transform_kernel<<<')[1].split('enable_bidirectional_uncer);')[0]
        self.assertEqual(a,b)
    def test_U_update_body_unchanged(self):
        a=self.original.split('    if (enable_update_uncer)')[1].split('\n  }\n\n')[0]
        b=self.entry.split('    if (enable_update_uncer)')[1].split('    trace.push_back(poses.detach()')[0].rstrip()
        self.assertEqual(a.rstrip(),b)
    def test_native_iterations_not_split_into_calls(self):
        self.assertEqual(self.entry.count('for (int itr=0; itr<iterations; itr++)'),1)
        self.assertNotIn('clamp',self.entry)
    def test_U_update_occurs_after_retraction(self):
        self.assertLess(self.entry.index('disp_retr_kernel<<<'),self.entry.index('if (enable_update_uncer)'))
    def test_motion_and_depth_only_forbidden(self):self.assertIn('TORCH_CHECK(!motion_only && !depth_only',self.entry)
    def test_original_LLT_method_unchanged(self):
        self.assertIn('dx = H.solve(lm, ep);',self.entry);self.assertEqual(self.cu.count('Eigen::SimplicialLLT<Eigen::SparseMatrix<double>> solver;'),1)
    def test_row_major_matrix_export(self):self.assertIn('a[r][c]=input.coeff(r,c)',self.cu)
    def test_diagnostic_schema_count(self):self.assertEqual(len(TRACE_NAMES),22)
    def test_dirty_source_fails_closed(self):
        with self.assertRaises(ValueError):build(self.raw+b'\n')
    def test_no_model_import_in_CPU_tests(self):self.assertNotIn('torch',sys.modules)

class RecordResult(unittest.TextTestResult):
    def startTest(self,test):self.started=time.perf_counter();super().startTest(test)
    def addSuccess(self,test):
        super().addSuccess(test);self.events.append({'test':test.id(),'status':'PASS','seconds':time.perf_counter()-self.started})
    def addFailure(self,test,err):
        super().addFailure(test,err);self.events.append({'test':test.id(),'status':'FAIL','traceback':self._exc_info_to_string(err,test)})
    def addError(self,test,err):
        super().addError(test,err);self.events.append({'test':test.id(),'status':'ERROR','traceback':self._exc_info_to_string(err,test)})
    def __init__(self,*a,**k):super().__init__(*a,**k);self.events=[]

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2,resultclass=RecordResult).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    report={'schema':'TASK005B_CPU_CONTRACT_TESTS_V1','passed':len(result.events)-len(result.failures)-len(result.errors),'total':result.testsRun,'PASS':result.wasSuccessful(),'seed':105,'scope':'CPU_SYNTHETIC_AND_SOURCE_ONLY','native_GPU_equivalence':'NOT_EXECUTED','events':result.events,'numpy':np.__version__}
    (ROOT/'04_tests/CPU_TEST_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='events'}));sys.exit(not result.wasSuccessful())
