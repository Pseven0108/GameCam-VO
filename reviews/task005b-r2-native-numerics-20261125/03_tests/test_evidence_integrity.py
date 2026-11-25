import unittest,pathlib,json,sys,hashlib,csv
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'04_analysis'))
from analyze_pairs import RECV,compare,FINAL,np
class Evidence(unittest.TestCase):
 def test_exactly_ten_completed_two_iteration_calls(self):
  receipts=list(RECV.rglob('*.receipt.json'));self.assertEqual(len(receipts),10)
  for p in receipts:
   j=json.loads(p.read_text());self.assertTrue(j['complete'] and j['all_finite']);self.assertEqual(j['scalars']['iterations'],2)
   self.assertTrue(j['metadata_and_alias_verified'] and j['rng_restored'])
 def test_same_real_input_hash_and_base_values(self):
  receipts=[json.loads(p.read_text()) for p in RECV.rglob('*.receipt.json')]
  self.assertEqual(len({j['state_sha256'] for j in receipts}),1)
  self.assertEqual(len({json.dumps(j['cloned_tensor_hashes'],sort_keys=True) for j in receipts}),1)
 def test_original_and_candidate_hash_differences_confined_to_prior(self):
  j=[json.loads(p.read_text()) for p in RECV.rglob('*.receipt.json')]
  for name in j[0]['effective_tensor_hashes']:
   count=len({r['effective_tensor_hashes'][name] for r in j})
   self.assertEqual(count,2 if name=='selected_prior' else 1)
 def test_all_binary_outputs_match_receipt_hash(self):
  for p in RECV.rglob('*.receipt.json'):
   j=json.loads(p.read_text());b=p.with_name(j['tag']+'.npz').read_bytes()
   self.assertEqual(len(b),j['output_bytes']);self.assertEqual(hashlib.sha256(b).hexdigest(),j['output_sha256'])
 def test_same_atol_as_original_float32_allclose(self):
  arrays=[dict(np.load(p,allow_pickle=False)) for p in (RECV/'plain').glob('*.npz')]
  for a in arrays:
   for b in arrays:
    for n in FINAL:self.assertEqual(compare(a[n],b[n])['PASS'],bool(np.allclose(a[n],b[n],atol=1e-6,rtol=1e-5,equal_nan=False)))
 def test_first_iteration_bitwise_matches_all_trace_paths(self):
  arrays=[dict(np.load(p,allow_pickle=False)) for p in (RECV/'trace').glob('*.npz')]
  for a in arrays:
   for n in ['iter1_dx','iter1_dz','iter1_C','iter1_w','iter1_Jii_data']:
    self.assertTrue(np.array_equal(a[n],arrays[0][n]))
 def test_feedback_native_two_round_seam(self):
  for p in (RECV/'trace').glob('*.npz'):
   a=np.load(p,allow_pickle=False)
   for x,y in [('U_after','U_before'),('temp_after','temp_before'),('affine_after','affine_before')]:self.assertTrue(np.array_equal(a['iter1_'+x],a['iter2_'+y]))
 def test_all_forty_cpu_formula_checks_pass(self):
  rows=list(csv.DictReader((ROOT/'04_analysis/FEEDBACK_RECONSTRUCTION.csv').open()))
  self.assertEqual(len(rows),40);self.assertTrue(all(r['PASS']=='True' for r in rows))
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Evidence))
 (ROOT/'03_tests/EVIDENCE_TEST_REPORT.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'PASS':result.wasSuccessful()},indent=2)+'\n')
 raise SystemExit(0 if result.wasSuccessful() else 1)
