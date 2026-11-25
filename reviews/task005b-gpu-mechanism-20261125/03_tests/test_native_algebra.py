import pathlib,sys,unittest,io,json,time
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'05_analysis'))
import verify_native_algebra as a

class AlgebraTests(unittest.TestCase):
    def test_one_depth_two_poses_schur(self):
        E=np.arange(24,dtype=float).reshape(2,6,2)/10
        Q=np.array([[2.,3.]]);w=np.array([[.2,.4]])
        S,b=a.schur_from_cross_blocks(E,Q,w,np.array([7,7]),np.array([1,2]),np.array([7]),1,3)
        M=E.reshape(12,2)
        np.testing.assert_allclose(S,(M*Q[0])@M.T)
        np.testing.assert_allclose(b,M@(Q[0]*w[0]))
    def test_duplicate_blocks_preserve_cross_terms(self):
        E=np.ones((2,6,3));Q=np.ones((1,3));w=np.ones((1,3))
        S,b=a.schur_from_cross_blocks(E,Q,w,np.array([7,7]),np.array([1,1]),np.array([7]),1,2)
        np.testing.assert_array_equal(S,np.full((6,6),12.))
        np.testing.assert_array_equal(b,np.full(6,6.))
    def test_out_of_window_pose_excluded(self):
        E=np.ones((3,6,2));Q=np.ones((1,2));w=np.ones((1,2))
        S,b=a.schur_from_cross_blocks(E,Q,w,np.array([7,7,7]),np.array([0,1,2]),np.array([7]),1,2)
        np.testing.assert_array_equal(S,np.full((6,6),2.))
        np.testing.assert_array_equal(b,np.full(6,2.))
    def test_separate_depth_variables_do_not_cross(self):
        E=np.ones((2,6,2));Q=np.ones((2,2));w=np.ones((2,2))
        S,b=a.schur_from_cross_blocks(E,Q,w,np.array([7,8]),np.array([1,1]),np.array([7,8]),1,2)
        np.testing.assert_array_equal(S,np.full((6,6),4.))
        np.testing.assert_array_equal(b,np.full(6,4.))
    def test_native_zero_index_guard_is_preserved(self):
        E=np.ones((2,6,2));dx=np.ones((2,6))
        got=a.native_depth_coupling(E,dx,np.array([7,7]),np.array([1,2]),np.array([7]),1)
        np.testing.assert_array_equal(got,[[6.,6.]])
    def test_source_index_union(self):
        src,tgt,kx=a.indices({'ii':np.array([0,3,5]),'jj':np.array([4,5,2])},{'t0':2,'t1':4})
        np.testing.assert_array_equal(src,[2,3,0,3,5])
        np.testing.assert_array_equal(tgt,[2,3,4,5,2])
        np.testing.assert_array_equal(kx,[0,2,3,5])

if __name__=='__main__':
    started=time.time();stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AlgebraTests))
    (ROOT/'03_tests/NATIVE_ALGEBRA_UNIT_TESTS.stdout.txt').write_text(stream.getvalue())
    (ROOT/'03_tests/NATIVE_ALGEBRA_UNIT_TESTS.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'PASS':result.wasSuccessful(),'seconds':time.time()-started,'GPU_used':False},indent=2))
    print(stream.getvalue());raise SystemExit(0 if result.wasSuccessful() else 1)
