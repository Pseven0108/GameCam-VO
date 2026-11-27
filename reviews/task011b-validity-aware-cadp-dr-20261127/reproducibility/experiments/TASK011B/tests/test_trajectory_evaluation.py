"""Known rigid/similarity invariance; synthetic test data never VO results."""
import sys,unittest
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from evaluate_viper import relative_metrics,legacy


class PoseEvaluation(unittest.TestCase):
    def setUp(self):
        t=np.linspace(0,3,64);gt=np.repeat(np.eye(4)[None],64,axis=0)
        gt[:,:3,3]=np.c_[t,np.sin(t),np.cos(.4*t)]
        gt[:,:3,:3]=Rotation.from_euler('z',t*.1).as_matrix()
        q=Rotation.from_euler('xyz',[.4,-.7,1.1]).as_matrix();shift=np.array([3.,-2.,4.]);s=2.3
        p=((gt[:,:3,3]-shift)@q)/s;r=q.T@gt[:,:3,:3]
        self.pred=np.c_[p,Rotation.from_matrix(r).as_quat()];self.gt=gt;self.ids=np.arange(1,65)

    def test_Sim3_rotates_both_positions_and_orientations(self):
        for offset in (1,15,60):
            result=relative_metrics(self.pred,self.gt,self.ids,offset,True)
            self.assertLess(result['translation_rmse'],1e-12)
            self.assertLess(result['rotation_rmse_deg'],1e-10)

    def test_raw_scale_error_not_hidden(self):
        result=relative_metrics(self.pred,self.gt,self.ids,15,False)
        self.assertGreater(result['translation_rmse'],.01)

    def test_constant_trajectory_not_given_fake_Sim3(self):
        with self.assertRaises(ValueError):legacy.fit_alignment(np.zeros((64,3)),self.gt[:,:3,3],True)


if __name__=='__main__':unittest.main(verbosity=2)
