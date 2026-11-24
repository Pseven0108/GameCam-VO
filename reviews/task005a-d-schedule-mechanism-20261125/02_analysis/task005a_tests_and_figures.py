"""CPU-only independent checks and diagnostic figures for TASK005A."""
import os,sys,pathlib,json,csv,math,unittest,io,hashlib
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
import numpy as np
from task005a_analysis import ROOT,OLD,ARMS,OUT,GT,stage,transform,align,quat,sha,dump,verify_seal

def rows(n):
 with (OUT/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def toy():
 truth=np.array([1.,2.]);prior=2.5;alpha=.01;eta=1e-7;out=[]
 for name,j,noise in [('well_conditioned_geometry',np.array([[1.,1.],[1.,2.]]),np.zeros(2)),('near_collinear_noisy_geometry',np.array([[1.,1.],[1.,1.001]]),np.array([.001,-.001]))]:
  y=j@truth+noise;a=j.T@j;b=j.T@y
  for D in [0,1]:
   normal=a.copy();rhs=b.copy();normal[1,1]+=alpha if D else eta
   if D:rhs[1]+=alpha*prior
   p=np.linalg.solve(normal,rhs)
   out.append(dict(geometry=name,D=D,pose=p[0],depth=p[1],pose_absolute_error=abs(p[0]-truth[0]),normal_condition_number=float(np.linalg.cond(normal)),prior_depth=prior,true_depth=2.,illustration_only_NOT_native_reconstruction=True))
 return out

class Checks(unittest.TestCase):
 def test_01_w2c_inverse(self):
  q=[0,0,np.sin(.3),np.cos(.3)];p=[1.2,-2,3,*q];c=transform(p,True);w=transform(p);np.testing.assert_allclose(w@c,np.eye(4),atol=1e-14)
 def test_02_sim3_fit(self):
  rng=np.random.default_rng(5001);x=rng.normal(size=(50,3));r=quat([.1,.2,.3,.9]);y=3.2*x@r.T+[1,2,3];rr,t,s=align(x,y);np.testing.assert_allclose(s*x@rr.T+t,y,atol=2e-14)
 def test_03_sim3_gauge_invariance(self):
  rng=np.random.default_rng(5002);x=rng.normal(size=(60,3));y=x+rng.normal(size=(60,3))*.1
  vals=[]
  for xx in (x,x*712.5+[8,9,10]):
   r,t,s=align(xx,y);vals.append(np.mean(np.sum((s*xx@r.T+t-y)**2,axis=1)))
  self.assertAlmostEqual(*vals,places=12)
 def test_04_common_support_exactly_72(self):
  s=json.loads((OUT/'COMMON_SUPPORT.json').read_text());self.assertEqual(s['count'],72);self.assertEqual(len(set(s['common_rgb_ids'])),72)
 def test_05_common_support_scores_all_equal_n(self):
  rs=[r for r in rows('TASK005A_MATCHED_SUPPORT_STAGE_SCORES.csv') if r['support']=='COMMON_ALL_FOUR_KF'];self.assertEqual(len(rs),12);self.assertTrue(all(int(r['n'])==72 for r in rs))
 def test_06_unavailable_KF_not_filled(self):
  rs=[r for r in rows('TASK005A_STAGE_ENDPOINTS.csv') if r['arm'] in ('B3','B4') and r['stage']!='EXPORTED' and r['start']=='312' and r['end']=='328'];self.assertEqual(len(rs),4);self.assertTrue(all(r['status']=='ENDPOINT_UNAVAILABLE' and not r['ratio_pct'] for r in rs))
 def test_07_reversal_precedes_final(self):
  rs=rows('TASK005A_CONDITIONAL_D_EFFECTS.csv');self.assertEqual(len(rs),4);self.assertTrue(all(float(r['D_on_minus_off_S1'])>0 and float(r['D_on_minus_off_S0'])<0 for r in rs))
 def test_08_all_four_first_BA_inputs_equal(self):
  x=json.loads((OUT/'TASK005A_SAME_SCHEDULE_CONTROL_CHECKS.json').read_text());self.assertTrue(x['all_four_first_BA_six_tensor_hashes_equal']);self.assertEqual(x['first_BA_rgb'],19);self.assertEqual(len(x['hash_keys']),6)
 def test_09_discrete_structure_fixed(self):
  x=json.loads((OUT/'TASK005A_SAME_SCHEDULE_CONTROL_CHECKS.json').read_text());self.assertEqual([v['local_calls'] for v in x['checks']],[839,757]);self.assertTrue(all(v['local_discrete_structure_exact_match'] for v in x['checks']))
 def test_10_local_D_scope(self):
  rs=[r for r in rows('TASK005A_BA_MECHANISM_TIMELINE.csv') if r['stage'].startswith('frontend_local_')];self.assertEqual(len(rs),3192);self.assertTrue(all((r['D_selected']=='True')==(r['D']=='1') for r in rs));self.assertTrue(all(r['source_UBA']=='True' and r['update_U']=='True' for r in rs))
 def test_11_native_grid_finite(self):
  rs=rows('TASK005A_BA_MECHANISM_TIMELINE.csv');self.assertEqual(len(rs),4756);self.assertTrue(all(float(r['native_full_nonfinite'])==0 for r in rs))
 def test_12_clamp_scope_valid(self):
  rs=rows('TASK005A_BA_MECHANISM_TIMELINE.csv');self.assertTrue(all(0<=float(r['native_full_negative_fraction'])<=float(r['clamp_grid_floor_fraction'])+1e-12<=1+1e-12 for r in rs))
 def test_13_prior_identity_at_common_support(self):
  s=json.loads((OUT/'DEPTH_PRIOR_INPUT_IDENTITY.json').read_text());self.assertTrue(s['all_equal']);self.assertEqual(s['common_count'],72)
 def test_14_kernel_matches_frozen_commit(self):
  x=json.loads((ROOT/'01_source_audit/SOURCE_PROVENANCE.json').read_text());self.assertEqual(x['baseline']['status'],'GIT_OBJECT_MATCH');self.assertTrue(x['kernel_source_copies_equal'])
 def test_15_forced_schedule_mismatches(self):
  rs={r['arm']:r for r in rows('TASK005A_MISMATCH_DIRECTION.csv')};self.assertEqual([int(rs[a]['mismatches']) for a in ['B1','B2','B4','B3']],[0,50,0,26]);self.assertTrue(all(int(r['mismatches'])==int(r['would_keep_but_forced_drop'])+int(r['would_drop_but_forced_keep']) for r in rs.values()))
 def test_16_weighted_events_are_not_replicates(self):
  self.assertTrue(all(r['estimation']=='DESCRIPTIVE_SINGLE_SEQUENCE_SINGLE_SEED_NOT_POPULATION_EFFECT' for r in rows('TASK005A_CONDITIONAL_D_EFFECTS.csv')))
 def test_17_fullsolve_matches_Schur(self):
  rng=np.random.default_rng(5003);e=rng.normal(size=(3,5));c=rng.uniform(.5,2,size=5);a=rng.normal(size=(3,3));a=a@a.T+e@np.diag(1/c)@e.T+np.eye(3);v=rng.normal(size=3);w=rng.normal(size=5)
  full=np.linalg.solve(np.block([[a,e],[e.T,np.diag(c)]]),np.r_[v,w]);dx=np.linalg.solve(a-e@np.diag(1/c)@e.T,v-e@(w/c));dz=(w-e.T@dx)/c
  np.testing.assert_allclose(np.r_[dx,dz],full,atol=2e-14)
 def test_18_regularizer_can_reverse_with_geometry(self):
  rs=toy();self.assertGreater(rs[1]['pose_absolute_error'],rs[0]['pose_absolute_error']);self.assertLess(rs[3]['pose_absolute_error'],rs[2]['pose_absolute_error'])
 def test_19_U_gate_threshold(self):
  u=np.array([0,.6,.8,.9,1.]);f=np.clip(1/np.maximum(45*u-35,.1),0,1);np.testing.assert_array_equal(f<1,u>.8)
 def test_20_export_and_postfinal_KF_agree(self):
  for a in ARMS:
   ss={r['stage']:float(r['ate_sim3']) for r in rows('TASK005A_MATCHED_SUPPORT_STAGE_SCORES.csv') if r['arm']==a and r['support']=='COMMON_ALL_FOUR_KF'};self.assertLess(abs(ss['EXPORTED']-ss['POST_FINAL_BA']),1e-4)
 def test_21_GT_identity_and_mapping(self):
  self.assertEqual(sha(GT),'91fb149c066bb488ac6071602a4b50fe1540243f2db3369a3706f63b705d7008')
  with np.load(GT,allow_pickle=False) as z:np.testing.assert_array_equal(z['rgb_ids'],np.arange(1,488));np.testing.assert_array_equal(z['camera_frame_ids'],np.arange(487))
 def test_22_sealed_experiment_unmodified(self):verify_seal()

def figures():
 sys.path.insert(0,str(RECEIVER_PATH/'cpu_plot_dependencies'))
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':150})
 figdir=ROOT/'04_figures';colors={'B1':'#b84a3a','B2':'#287b58','B4':'#5076a4','B3':'#a6771c'}
 scores=rows('TASK005A_MATCHED_SUPPORT_STAGE_SCORES.csv')
 fig,axs=plt.subplots(1,2,figsize=(10.8,4.3),layout='constrained')
 for ax,(s,arms) in zip(axs,[('S1',['B1','B2']),('S0',['B3','B4'])]):
  for a in arms:
   vals=[next(float(r['ate_sim3']) for r in scores if r['arm']==a and r['stage']==st and r['support']=='COMMON_ALL_FOUR_KF') for st in ['FRONTEND','POST_FINAL_BA','EXPORTED']]
   ax.plot(range(3),vals,'o-',color=colors[a],label=a+' / D='+str(ARMS[a][0]));
   for i,v in enumerate(vals[:2]):ax.annotate(f'{v:.2f}',(i,v),xytext=(0,8),textcoords='offset points',ha='center',fontsize=9)
  ax.set_xticks(range(3),['Frontend','Final BA','Export KF']);ax.set_ylabel('Sim(3) ATE / game units');ax.set_title(s+' / identical 72-frame support');ax.legend();ax.grid(alpha=.2)
 fig.suptitle('D effect reverses before Final BA; reversal survives matched support');fig.savefig(figdir/'01_MATCHED_STAGE_REVERSAL.png');plt.close(fig)
 pr=rows('TASK005A_PREFIX_CONDITIONAL_EFFECTS.csv');fig,ax=plt.subplots(figsize=(10.8,4.1),layout='constrained')
 x=[int(r['trigger_rgb']) for r in pr]
 for key,label,col in [('D_on_minus_off_S1','S1: D on minus off','#b84a3a'),('D_on_minus_off_S0','S0: D on minus off','#5076a4')]:ax.plot(x,[float(r[key]) for r in pr],label=label,color=col)
 ax.axhline(0,color='black',linewidth=.8);ax.set_xlabel('Trigger RGB frame');ax.set_ylabel('Conditional ATE difference / game units');ax.set_title('Current-prefix common KF support after last predecision BA');ax.legend();ax.grid(alpha=.2)
 fig.savefig(figdir/'02_PREFIX_CONDITIONAL_EFFECTS.png');plt.close(fig)
 rs=[r for r in rows('TASK005A_BA_PHASE_SUMMARY.csv') if r['stage']=='frontend_local_predecision'];by={r['arm']:r for r in rs};arms=list(ARMS)
 fig,axs=plt.subplots(2,2,figsize=(10.8,7),layout='constrained')
 specs=[('native_full_negative_fraction_event_median',100,'Native negative disparity (%)'),('clamp_grid_floor_fraction_event_median',100,'Post-clamp floor fraction (%)'),('source_U_multiplier_mean_event_median',1,'Mean source U multiplier'),('edge_rgb_gap_p90_event_median',1,'Edge frame-gap P90')]
 for ax,(key,mul,title) in zip(axs.flat,specs):
  vals=[float(by[a][key])*mul for a in arms];ax.bar(arms,vals,color=[colors[a] for a in arms]);ax.set_title(title)
  for i,v in enumerate(vals):ax.annotate(f'{v:.3g}',(i,v),xytext=(0,4),textcoords='offset points',ha='center')
  ax.set_ylim(0,max(vals)*1.2);ax.grid(axis='y',alpha=.2)
 fig.suptitle('Predecision BA: medians across events are descriptive, not independent trials');fig.savefig(figdir/'03_LOCAL_DIAGNOSTICS.png');plt.close(fig)
 with np.load(GT,allow_pickle=False) as z:gt=z['c2w'][:,:3,3]
 axes=np.argsort(np.var(gt,axis=0))[-2:];labels=['X','Y','Z'];fig,axs=plt.subplots(2,2,figsize=(10.8,8),layout='constrained')
 for ax,a in zip(axs.flat,arms):
  arr=np.loadtxt(stage(a)/'native/traj/est_poses_full.txt');x=arr[:,1:4];rot,t,s=align(x,gt);p=s*x@rot.T+t
  ax.plot(gt[:,axes[0]],gt[:,axes[1]],color='#292929',label='GT');ax.plot(p[:,axes[0]],p[:,axes[1]],color=colors[a],label=a+' / D='+str(ARMS[a][0])+' / '+ARMS[a][1]);ax.set_aspect('equal',adjustable='datalim');ax.legend(fontsize=8);ax.set_xlabel('GT world '+labels[axes[0]]);ax.set_ylabel('GT world '+labels[axes[1]]);ax.grid(alpha=.2)
 fig.suptitle('Final 487 poses / one global Sim(3) per complete trajectory / game units');fig.savefig(figdir/'04_GLOBAL_ALIGNED_TRAJECTORIES.png');plt.close(fig)
 dump(ROOT/'05_tests/PLOTTING_ENVIRONMENT.json',{'matplotlib':matplotlib.__version__,'numpy':np.__version__,'backend':'Agg','figure_count':4,'world_axes_plotted':axes.tolist()})

RECEIVER_PATH=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125')
if __name__=='__main__':
 dump(OUT/'TASK005A_SYNTHETIC_SCHUR_ILLUSTRATION.json',{'status':'ILLUSTRATION_ONLY_NOT_NATIVE_REPLAY','alpha':.01,'eta':1e-7,'results':toy()})
 runner=unittest.TextTestRunner(stream=sys.stdout,verbosity=2);res=runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
 dump(ROOT/'05_tests/TASK005A_CPU_TEST_REPORT.json',{'tests_run':res.testsRun,'failures':len(res.failures),'errors':len(res.errors),'status':'PASS' if res.wasSuccessful() else 'FAIL','synthetic_random_seeds':[5001,5002,5003],'native_execution':False,'new_GPU_runs':0,'tests':[t for t in unittest.defaultTestLoader.getTestCaseNames(Checks)],'limits':'Checks validate offline analysis and controls; they do not validate native solver optimality or primary root cause.'})
 if not res.wasSuccessful():raise SystemExit(1)
 figures();verify_seal();print('CPU_CHECKS_AND_FIGURES_COMPLETE',flush=True)
