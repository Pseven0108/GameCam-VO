import unittest,sys,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'04_analysis'))
from numerics import *
class NumericalContract(unittest.TestCase):
    def test_identical(self):self.assertTrue(compare(np.array([1.],dtype='f4'),np.array([1.],dtype='f4'))['bitwise_equal'])
    def test_unmodified_tolerance_failure(self):self.assertFalse(compare(np.array([0.],dtype='f4'),np.array([2e-6],dtype='f4'))['PASS'])
    def test_relative_tolerance(self):self.assertTrue(compare(np.array([100.],dtype='f4'),np.array([100.0005],dtype='f4'))['PASS'])
    def test_one_ULP(self):
        a=np.array([1.],dtype='f4');b=np.nextafter(a,np.float32(2.));self.assertEqual(compare(a,b)['max_ULP'],1)
    def test_negative_ULP(self):
        a=np.array([-1.],dtype='f4');b=np.nextafter(a,np.float32(-2.));self.assertEqual(compare(a,b)['max_ULP'],1)
    def test_zero_range(self):self.assertEqual(dispersion([np.ones(2)]*4)['variable_elements'],0)
    def test_variable_range(self):self.assertEqual(dispersion([np.array([x,0]) for x in range(4)])['max_range'],3.)
    def test_lower_triangle_semantics(self):
        a=np.array([[2,99],[1,3.]],dtype='f8');sym=np.tril(a)+np.tril(a,-1).T;self.assertEqual(sym[0,1],1.)
if __name__=='__main__':unittest.main(verbosity=2)
