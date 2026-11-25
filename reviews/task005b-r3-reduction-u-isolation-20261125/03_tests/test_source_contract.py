import unittest,pathlib,re,json
ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=(ROOT.parent/'GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1/02_candidate/task005b_kernels.cu').read_text(encoding='utf-8')
SRC=(ROOT/'02_candidate/task005b_r3_kernels.cu').read_text(encoding='utf-8')
RUN=(ROOT/'01_runtime/replay_r3.py').read_text(encoding='utf-8')
def kernel(text,name):
    i=text.index('__global__ void '+name+'(');return text[i:text.index('\n}\n',i)+3]
class SourceContract(unittest.TestCase):
    def test_original_prefix_preserved(self):self.assertTrue(SRC.startswith(BASE))
    def test_jjj_kernel_unchanged(self):self.assertEqual(kernel(SRC,'dino_feats_projective_transform_kernel'),kernel(BASE,'dino_feats_projective_transform_kernel'))
    def test_linear_kernel_unchanged(self):self.assertEqual(kernel(SRC,'linear_transform_kernel'),kernel(BASE,'linear_transform_kernel'))
    def test_update_kernel_unchanged(self):self.assertEqual(kernel(SRC,'uncertainty_update_kernel'),kernel(BASE,'uncertainty_update_kernel'))
    def test_U_only_restore_two_copies(self):self.assertEqual(SRC.count('if (freeze_U) uncertainties.copy_(frozen_U);'),2)
    def test_U_computed_before_intervention(self):
        for s in SRC.split(' // R3_U_ONLY_INTERVENTION')[:-1]:
            self.assertIn('R3_OBSERVE U_computed',s[-350:])
    def test_trace_schema_unique(self):
        names=json.loads((ROOT/'02_candidate/TRACE_SCHEMA.json').read_text());self.assertEqual(len(names),len(set(names)))
        self.assertTrue({'U_computed','U_after','H_raw','L_damped_raw','Jjj_data','J_linear'}<=set(names))
    def test_updater_not_disabled(self):self.assertNotIn("s['enable_update_uncer']=False",RUN)
    def test_no_model_or_full_prefix(self):
        for forbidden in ['load_state_dict','Droid(','Tracker(','track(','safetensors','torch.hub']:
            self.assertNotIn(forbidden,RUN)
    def test_original_zero_prior_paths_real(self):self.assertIn("args[3]=c['cached_mono'] if is_paths else torch.zeros_like(c['selected_prior'])",RUN)
    def test_fixed_linear_not_from_isolated_jjj(self):
        self.assertIn("largs=[sealed['iter1_J_total']",RUN);self.assertIn("'upstream_r3_results_used':False",RUN)
    def test_exact_two_iterations_and_call_budget(self):self.assertIn("s['iterations']==2",RUN);self.assertIn('assert calls==20',RUN)
    def test_no_tolerance_relaxation(self):
        p=(ROOT/'PROTOCOL.md').read_text(encoding='utf-8');self.assertIn('atol=1e-6、rtol=1e-5',p)
    def test_build_separate_module(self):
        b=(ROOT/'02_candidate/build_r3.py').read_text();self.assertIn("name='gamecam_task005b_r3_isolation'",b);self.assertNotIn('copyfile',b)
if __name__=='__main__':unittest.main(verbosity=2)
