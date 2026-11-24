"""Independent geometric oracles plus actual replay-evidence contract checks (CPU only)."""
import os,sys,pathlib,json,unittest,hashlib,csv,io,time
import numpy as np
from geometry_analysis import qrot,qmul
ROOT=pathlib.Path(__file__).resolve().parents[1]
A=pathlib.Path(r'D:/aaa/GameCam-VO/experiments/DROID_W_TASK004A_GPU_SCREENING_20261123T082038066Z')
sys.path.insert(0,str(A/'release/tools'));import endpoints as ep

def read(p):return json.loads((ROOT/p).read_text(encoding='utf8'))
def quat_matrix(q):
 q=np.asarray(q);u=q[:3];w=q[3];S=np.array([[0,-u[2],u[1]],[u[2],0,-u[0]],[-u[1],u[0],0]])
 return np.eye(3)+2*w*S+2*S@S
class MathEvidence(unittest.TestCase):
 def test_rotation_vector_vs_matrix(self):
  rng=np.random.default_rng(9043)
  for _ in range(30):
   q=rng.normal(size=4);q/=np.linalg.norm(q);x=rng.normal(size=(16,3));np.testing.assert_allclose(qrot(q,x),x@quat_matrix(q).T,atol=2e-14,rtol=0)
 def test_relative_projection_homogeneous_vs_worldpoint(self):
  rng=np.random.default_rng(9044)
  for _ in range(30):
   qi=rng.normal(size=4);qi/=np.linalg.norm(qi);qj=rng.normal(size=4);qj/=np.linalg.norm(qj);ti=rng.normal(size=3);tj=rng.normal(size=3);ray=np.array([.2,-.3,1.]);d=.7
   Ri,Rj=quat_matrix(qi),quat_matrix(qj);world=Ri.T@(ray/d-ti);point=Rj@world+tj
   q=qmul(qj,qi*np.array([-1,-1,-1,1]));t=tj-qrot(q,ti);hom=qrot(q,ray)+d*t
   np.testing.assert_allclose(hom,d*point,atol=1e-14,rtol=0)
 def test_depth_jacobian_finite_difference(self):
  ray=np.array([.17,-.13,1.]);t=np.array([.08,.02,-.03]);d=.8;f=np.array([51.,52.]);eps=1e-6;v=ray+d*t
  oracle=f*(t[:2]/v[2]-t[2]*v[:2]/v[2]**2)
  def proj(dd):p=ray+dd*t;return f*p[:2]/p[2]
  np.testing.assert_allclose(oracle,(proj(d+eps)-proj(d-eps))/(2*eps),atol=2e-8,rtol=0)
 def test_w2c_inverse_oracle(self):
  q=np.array([.1,.2,.3,.9]);q/=np.linalg.norm(q);v=np.r_[[1.,2.,3.],q];P=ep.pose_matrix(v,'W2C');T=np.eye(4);T[:3,:3]=quat_matrix(q);T[:3,3]=v[:3];np.testing.assert_allclose(T@P,np.eye(4),atol=1e-14)
 def test_camera_relative_motion_gauge_invariance(self):
  q=np.array([.3,-.2,.1,.8]);q/=np.linalg.norm(q);R=quat_matrix(q);P=np.eye(4);Q=np.eye(4);Q[:3,3]=[1,2,3];G=np.eye(4);G[:3,:3]=R;G[:3,3]=[7,2,9]
  def rel(p,q):return p[:3,:3].T@(q[:3,3]-p[:3,3])
  np.testing.assert_allclose(rel(P,Q),rel(G@P,G@Q),atol=1e-14)
 def test_cpu_only(self):
  self.assertEqual(os.environ.get('CUDA_VISIBLE_DEVICES'),'');self.assertNotIn('torch',sys.modules)
 def test_both_real_states_eligible(self):
  for arm in ['E0','E1']:
   m=read('native_small/'+arm+'/CHECKPOINT.json');self.assertTrue(m['eligibility']['both_in_optimized_window']);self.assertTrue(m['eligibility']['both_directed_edges']);self.assertEqual(m['trigger_rgb'],328);self.assertFalse(m['historical_state_reconstruction']);self.assertFalse(m['frontend_restart_complete'])
 def test_only_prior_input_differs_within_state(self):
  for arm in ['E0','E1']:
   one=read('native_small/'+arm+'_D1/INPUT_RESTORATION.json');zero=read('native_small/'+arm+'_D0/INPUT_RESTORATION.json');self.assertEqual(one['common_input_digest'],zero['common_input_digest']);self.assertTrue(one['all_hashes_exact'] and zero['all_hashes_exact']);self.assertEqual(set(one['input_hashes']),set(zero['input_hashes']))
   for name in one['input_hashes']:
    if name!='selected_prior':self.assertEqual(one['input_hashes'][name],zero['input_hashes'][name])
   self.assertEqual(one['input_hashes']['selected_prior']['source'],'mono_disps');self.assertEqual(zero['input_hashes']['selected_prior']['source'],'zeros');self.assertNotEqual(one['input_hashes']['selected_prior']['data_sha256'],zero['input_hashes']['selected_prior']['data_sha256'])
 def test_rgb_stream_equal(self):
  a=read('native_small/E0/CHECKPOINT.json');b=read('native_small/E1/CHECKPOINT.json');self.assertEqual(a['scaled_prefix_rgb_sha256'],b['scaled_prefix_rgb_sha256'])
 def test_four_single_native_calls(self):
  for arm in ['E0_D1','E0_D0','E1_D1','E1_D0']:
   r=read('native_small/'+arm+'/REPLAY_COMPLETE.json');s=read('native_small/'+arm+'/STATUS.json');self.assertEqual(r['native_ba_calls'],1);self.assertEqual(r['native_inner_iterations'],2);self.assertTrue(r['all_immutable_inputs_unchanged']);self.assertFalse(r['model_constructed']);self.assertFalse(r['network_forward']);self.assertEqual(r['nonfinite_active'],0);self.assertEqual(s['exit_code'],0)
 def test_restored_small_arrays_and_pose_geometry(self):
  for arm in ['E0','E1']:
   m=read('native_small/'+arm+'/CHECKPOINT.json');ids=np.load(ROOT/'native_small'/arm/'timestamp.npy',allow_pickle=False)[:m['active_count']].astype(int)+1;self.assertEqual(list(ids).count(312),1);self.assertEqual(list(ids).count(328),1)
   for D in [1,0]:
    p=ROOT/'native_small'/f'{arm}_D{D}'/'poses_native.npy';r=read(f'native_small/{arm}_D{D}/REPLAY_COMPLETE.json');self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),r['arrays']['poses_native']['file_sha256']);poses=np.load(p,allow_pickle=False)
    for row in poses[:m['active_count']]:ep.rigid(ep.pose_matrix(row,'W2C'))
 def test_analysis_real_exit_codes(self):
  self.assertEqual(read('results/ANALYSIS_PROCESS.json')['exit_code'],0);self.assertEqual(read('results/COMMON_SUPPORT_PROCESS.json')['exit_code'],0);self.assertFalse(read('results/COMMON_SUPPORT_PROCESS.json')['torch_imported'])
 def test_frozen_source_preservation(self):
  r=read('evidence/FINAL_INTEGRITY_AUDIT.json');self.assertTrue(r['all_protected_matches']);self.assertEqual(len(r['frozen_original_source']),208);self.assertFalse(r['shutdown']);self.assertEqual(r['gpu_compute_apps']['stdout'].strip(),'')
 def test_same_common_pixel_counts(self):
  with (ROOT/'results/COMMON_SUPPORT_RESIDUALS.csv').open() as f:rows=list(csv.DictReader(f))
  for a in ['E0','E1']:
   rs=[r for r in rows if r['state']==a];self.assertEqual(len(rs),3);self.assertEqual(len({r['common_valid_pixels'] for r in rs}),1);self.assertGreater(int(rs[0]['common_valid_pixels']),0)
if __name__=='__main__':
 start=time.monotonic();suite=unittest.defaultTestLoader.loadTestsFromTestCase(MathEvidence);buf=io.StringIO();r=unittest.TextTestRunner(stream=buf,verbosity=2).run(suite);print(buf.getvalue());out=dict(tests_run=r.testsRun,failures=len(r.failures),errors=len(r.errors),all_pass=r.wasSuccessful(),elapsed_seconds=time.monotonic()-start,random_seeds=[9043,9044],torch_imported='torch' in sys.modules,scope='CPU geometry oracles and actual sealed evidence checks; no new native BA execution');(ROOT/'results/ANALYSIS_VALIDATION_TEST_REPORT.json').write_text(json.dumps(out,indent=2));sys.exit(0 if r.wasSuccessful() else 1)
