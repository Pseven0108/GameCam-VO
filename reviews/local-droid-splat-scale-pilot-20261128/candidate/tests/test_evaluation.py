import pathlib,sys,unittest
import numpy as np
from scipy.spatial.transform import Rotation
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from evaluation import evaluate,fit_alignment,rpe

class Tests(unittest.TestCase):
    def setUp(self):
        tt=np.arange(64)*.04
        self.truth=np.broadcast_to(np.eye(4),(64,4,4)).copy()
        self.truth[:,:3,3]=np.stack([tt,.3*np.sin(tt),.2*np.cos(tt)],axis=-1)
        self.truth[:,:3,:3]=Rotation.from_euler('z',tt*.3).as_matrix()
        self.ids=np.arange(309,373)
    def test_identity(self):
        stats,_=evaluate(self.truth,self.truth,self.ids)
        self.assertLess(stats['ate_sim3_rmse'],1e-12);self.assertLess(stats['rpe15_translation_rmse'],1e-12)
        self.assertAlmostEqual(stats['raw_path_ratio'],1.)
    def test_known_sim3(self):
        q=Rotation.from_euler('xy',[.2,-.4]).as_matrix();pred=self.truth.copy()
        pred[:,:3,3]=(self.truth[:,:3,3]-[1,-2,.4])@q/3.5
        pred[:,:3,:3]=q.T@self.truth[:,:3,:3]
        stats,_=evaluate(pred,self.truth,self.ids)
        self.assertAlmostEqual(stats['global_sim3_scale'],3.5,places=10)
        self.assertLess(stats['ate_sim3_rmse'],1e-12);self.assertGreater(stats['ate_se3_rmse'],.1)
        self.assertLess(stats['rpe1_rotation_rmse_deg'],1e-10)
    def test_pair_offsets(self):
        stats,_=evaluate(self.truth,self.truth,self.ids)
        self.assertEqual(stats['rpe1_pairs'],63);self.assertEqual(stats['rpe15_pairs'],49)
    def test_gap_not_filled(self):
        p=self.truth[:,:3,3];r=self.truth[:,:3,:3]
        self.assertEqual(rpe(p,r,p,r,self.ids*3,1)['pairs'],0)
    def test_degenerate_stops(self):
        with self.assertRaises(ValueError):fit_alignment(np.zeros((5,3)),np.zeros((5,3)),True)
    def test_invalid_rotation_stops(self):
        pred=self.truth.copy();pred[0,0,0]=2
        with self.assertRaises(ValueError):evaluate(pred,self.truth,self.ids)

if __name__=='__main__':unittest.main(verbosity=2)
