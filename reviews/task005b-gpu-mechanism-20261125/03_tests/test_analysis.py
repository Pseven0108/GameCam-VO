import pathlib,sys,unittest,importlib.util,json,time,io
import numpy as np
r=pathlib.Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location('analysis',r/'05_analysis/analyze_native.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
class NumericalTests(unittest.TestCase):
 def test_identity_quaternion(self):np.testing.assert_array_equal(a.qmat([0,0,0,1]),np.eye(3))
 def test_quaternion_rotation(self):np.testing.assert_allclose(a.qmat([0,0,2**-.5,2**-.5])@np.array([1.,0,0]),[0,1,0],atol=1e-14)
 def test_projection_no_motion(self):
  p=np.zeros((2,7));p[:,6]=1.;d=np.ones((2,2,3));u,v=a.reprojection(p,d,[0],[1],np.array([2.,2.,1.,1.]));yy,xx=np.mgrid[:2,:3];np.testing.assert_allclose(u[0],np.stack([xx,yy]));self.assertTrue(v.all())
 def test_world_to_camera_translation(self):
  p=np.zeros((2,7));p[:,6]=1.;p[1,0]=.5;d=np.ones((2,2,3));u,v=a.reprojection(p,d,[0],[1],np.array([2.,2.,1.,1.]));yy,xx=np.mgrid[:2,:3];np.testing.assert_allclose(u[0,0],xx+1.);self.assertTrue(v.all())
 def test_stereo_baseline(self):
  p=np.zeros((1,7));p[:,6]=1.;u,v=a.reprojection(p,np.ones((1,2,3)),[0],[0],np.array([2.,2.,1.,1.]));yy,xx=np.mgrid[:2,:3];np.testing.assert_allclose(u[0,0],xx-.2)
 def test_min_depth_mask(self):
  p=np.zeros((2,7));p[:,6]=1.;p[1,2]=-1.;u,v=a.reprojection(p,np.ones((2,2,3)),[0],[1],np.array([2.,2.,1.,1.]));self.assertFalse(v.any())
 def test_solver_uses_lower_triangle(self):np.testing.assert_array_equal(a.sym_lower(np.array([[2.,999.],[1.,3.]])),[[2.,1.],[1.,3.]])
 def test_spd_spectrum(self):
  q=a.spectrum(np.diag([2.,8.]));self.assertTrue(q['SPD']);self.assertEqual(q['rank'],2);self.assertEqual(q['condition_2'],4.)
 def test_singular_spectrum(self):
  q=a.spectrum(np.diag([0.,8.]));self.assertFalse(q['SPD']);self.assertEqual(q['rank'],1);self.assertIsNone(q['condition_2'])
 def test_vector_factorial_identity(self):
  g=np.random.default_rng(43);A,B,C,D=g.normal(size=(4,3,6));cur=B-D;grad=C-D;inter=A-B-C+D;np.testing.assert_allclose(A-D,cur+grad+inter,atol=1e-14)
start=time.time();stream=io.StringIO();res=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NumericalTests));(r/'03_tests/ANALYSIS_UNIT_TESTS.stdout.txt').write_text(stream.getvalue());(r/'03_tests/ANALYSIS_UNIT_TESTS.json').write_text(json.dumps({'tests':res.testsRun,'failures':len(res.failures),'errors':len(res.errors),'PASS':res.wasSuccessful(),'seconds':time.time()-start,'GPU_used':False},indent=2));print(stream.getvalue());raise SystemExit(0 if res.wasSuccessful() else 1)
