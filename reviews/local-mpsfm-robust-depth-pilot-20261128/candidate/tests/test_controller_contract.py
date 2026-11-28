import pathlib,sys,unittest
TASK=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(TASK/'src'))
from robust_controller import eligible,MAIN,PASSTHROUGH
class StageTests(unittest.TestCase):
    def test_main_enabled(self):self.assertTrue(eligible(MAIN,False,True))
    def test_no_motion_only(self):self.assertFalse(eligible(MAIN,True,True))
    def test_no_depth_prior_disabled(self):self.assertFalse(eligible(MAIN,False,False))
    def test_initialization_untouched(self):self.assertFalse(eligible('INITIALIZATION',False,True))
    def test_initialization_second_untouched(self):self.assertFalse(eligible('INITIALIZATION_SECOND_STAGE',False,True))
    def test_final_ba_untouched(self):self.assertFalse(eligible('FINAL_GLOBAL_BA',False,True))
    def test_filler_untouched(self):self.assertFalse(eligible('TRAJECTORY_FILLER',True,True))
    def test_missing_stage_stops(self):
        with self.assertRaises(RuntimeError):eligible(None,False,True)
    def test_wrong_stage_stops(self):
        with self.assertRaises(RuntimeError):eligible('LOCAL',False,True)
if __name__=='__main__':unittest.main(verbosity=2)
