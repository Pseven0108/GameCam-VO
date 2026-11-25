import unittest,sys,pathlib,json,hashlib,glob
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'04_analysis'))
from numerics import *
class EvidenceIntegrity(unittest.TestCase):
    def test_exact_budget(self):
        c=json.loads((DATA/'COMPLETE.json').read_text());self.assertEqual(c['isolated_jjj_calls'],16);self.assertEqual(c['isolated_linear_calls'],16);self.assertEqual(c['two_iteration_BA_calls'],20)
    def test_native_run_exit(self):self.assertEqual(json.loads((RECV/'evidence/run/PROCESS_RECEIPT.json').read_text())['exit_code'],0)
    def test_every_output_hash(self):
        receipts=list(DATA.glob('*.receipt.json'));self.assertEqual(len(receipts),52)
        for p in receipts:
            r=json.loads(p.read_text());output=DATA/(r['tag']+'.npz');self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(),r['output_SHA']);self.assertTrue(r['complete'] and r['all_finite'])
    def test_fixed_U_is_only_restore(self):
        for group in ('reference_fixed','paths_fixed'):
            for i in range(1,5):
                a=load(f'{group}_{i:02d}')
                for it in (1,2):
                    self.assertTrue(np.array_equal(a[f'iter{it}_U_after'],a['iter1_U_before']))
                    self.assertFalse(np.array_equal(a[f'iter{it}_U_computed'],a[f'iter{it}_U_after']))
                    self.assertFalse(np.array_equal(a[f'iter{it}_affine_after'],a[f'iter{it}_affine_before']))
    def test_all_finite_loaded(self):
        for p in DATA.glob('*.npz'):
            with np.load(p,allow_pickle=False) as z:
                for n in z.files:self.assertTrue(np.isfinite(z[n]).all(),str(p)+':'+n)
    def test_input_unchanged(self):self.assertTrue(json.loads((DATA/'COMPLETE.json').read_text())['input_preserved'])
    def test_legacy_files_unchanged(self):self.assertTrue(json.loads((ROOT/'ORIGINAL_EVIDENCE_PRESERVATION.json').read_text())['all_protected_SHA_unchanged'])
    def test_no_expansion(self):
        p=(ROOT/'PROTOCOL.md').read_text(encoding='utf-8');self.assertIn('无S0',p);self.assertIn('无RGB前缀',p)
if __name__=='__main__':unittest.main(verbosity=2)
