"""Framework acceptance with synthetic CPU states, never real BA/model calls."""
import ast,csv,hashlib,io,json,os,random,subprocess,sys,tempfile,types,unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
import torch
TASK=Path(__file__).resolve().parents[1];sys.path.insert(0,str(TASK))
from collect_snapshots import (SnapshotCollector,argument_manifest,eligible,rng_capture,serialized_clone)
from fixed_state_replay import replay
from uniform_control import torch_uniform_for_call
from analyze_results import failure_accounting,paired_bootstrap,fsr_sequence_summary
from run_end_to_end import validate_plan
from authorization import require_approved_runtime

def arguments():
    a=[0. for _ in range(30)]
    a[0]=torch.zeros((4,7));a[1]=torch.ones((4,2,3));a[2]=torch.tensor([100.,100.,40.,20.]);a[3]=torch.ones((4,2,3))
    base=torch.arange(40.).reshape(4,10);a[4]=base[:,1:9:2];a[5]=base[:,2:10:2]
    for i in (6,7,8):a[i]=torch.zeros((4,2,3))
    a[9]=torch.zeros(5);a[10]=torch.ones((3,2,3))*.1;a[11]=torch.tensor([0,1,2]);a[12]=torch.tensor([1,2,3])
    a[13:16]=[1,3,2];a[20]=.01;a[23:30]=[False,False,True,True,True,False,False]
    return tuple(a)

def snapshot():
    args=arguments();r5=torch.zeros((4,2,3));r5[:3]=torch.tensor([[.1,.2,.3],[.5,.7,.9]])
    nv=torch.ones_like(r5,dtype=torch.bool);r7,meta=torch_uniform_for_call(r5,nv,args[3],torch.tensor([0,1,2]))
    return dict(args=args,a5=r5,a7=r7,native_valid=nv,source_metadata=meta,rng=rng_capture(),
        argument_manifest=argument_manifest(args),sequence='SYNTHETIC_SEQUENCE',seed=43,call=0,synthetic=True,phase='FRONTEND_MAIN_LOOP_LOCAL_BA')

class SyntheticCandidate:
    def __init__(self):self.initial=[]
    def ba(self,*args):
        assert len(args)==33 and args[-2:]==(True,False)
        self.initial.append(argument_manifest(args[:30]))
        strength=args[-3];weighted=(strength*torch.arange(6).reshape(2,3)).sum((1,2))
        args[0][:,0]+=weighted;args[1].add_(strength)
        if args[25]:args[6].add_(strength*.1)
        return weighted[:,None]+torch.rand((4,6)),strength.flatten(1),torch.zeros((2,3,4))

class SnapshotContracts(unittest.TestCase):
    def test_observer_does_not_advance_python_numpy_or_torch_RNG(self):
        s=snapshot();before=rng_capture()
        with tempfile.TemporaryDirectory(dir='D:/aaa/tmp/gamecam-vo') as tmp:
            c=SnapshotCollector(Path(tmp)/'snapshots','SYNTHETIC_SEQUENCE',43,synthetic=True)
            c.capture('FRONTEND_MAIN_LOOP_LOCAL_BA',s['args'],True,s['a5'],s['a7'],s['native_valid'],s['source_metadata'])
        after=rng_capture()
        self.assertEqual(before['python'],after['python']);self.assertEqual(before['numpy'],after['numpy'])
        self.assertTrue(torch.equal(before['torch_cpu'],after['torch_cpu']))
    def test_only_actual_eligible_phase(self):
        a=arguments()
        self.assertTrue(eligible('FRONTEND_MAIN_LOOP_LOCAL_BA',a,True))
        for phase in ('INITIALIZATION','INITIALIZATION_SECOND_STAGE','FINAL_GLOBAL_BA','ONLINE_GLOBAL_BA','TRAJECTORY_FILLER',None):self.assertFalse(eligible(phase,a,True))
        b=list(a);b[23]=True;self.assertFalse(eligible('FRONTEND_MAIN_LOOP_LOCAL_BA',b,True))
        self.assertFalse(eligible('FRONTEND_MAIN_LOOP_LOCAL_BA',a,False))
    def test_signature_must_be_complete(self):
        with self.assertRaises(ValueError):eligible('FRONTEND_MAIN_LOOP_LOCAL_BA',arguments()[:-1],True)
    def test_clone_preserves_alias_stride_offset_and_values(self):
        s=snapshot();c=serialized_clone(s)
        self.assertEqual(argument_manifest(c['args']),s['argument_manifest'])
        self.assertEqual(c['args'][4].untyped_storage().data_ptr(),c['args'][5].untyped_storage().data_ptr())
        self.assertNotEqual(c['args'][4].untyped_storage().data_ptr(),s['args'][4].untyped_storage().data_ptr())
    def test_disk_snapshot_and_original_protected(self):
        s=snapshot();before=argument_manifest(s['args'])
        with tempfile.TemporaryDirectory(dir='D:/aaa/tmp/gamecam-vo') as tmp:
            collector=SnapshotCollector(Path(tmp)/'snapshots','SYNTHETIC_SEQUENCE',43,synthetic=True)
            self.assertIsNone(collector.capture('INITIALIZATION',s['args'],True,s['a5'],s['a7'],s['native_valid'],s['source_metadata']))
            p=collector.capture('FRONTEND_MAIN_LOOP_LOCAL_BA',s['args'],True,s['a5'],s['a7'],s['native_valid'],s['source_metadata'])
            loaded=torch.load(p,weights_only=True);self.assertEqual(loaded['argument_manifest'],before)
            self.assertEqual(collector.count,1)
        self.assertEqual(argument_manifest(s['args']),before)
    def test_every_write_checks_storage(self):
        s=snapshot()
        with tempfile.TemporaryDirectory(dir='D:/aaa/tmp/gamecam-vo') as tmp:
            c=SnapshotCollector(Path(tmp)/'snapshots','SYNTHETIC_SEQUENCE',43,minimum_free=10**30,synthetic=True)
            with self.assertRaisesRegex(RuntimeError,'STORAGE_BLOCKED'):c.capture('FRONTEND_MAIN_LOOP_LOCAL_BA',s['args'],True,s['a5'],s['a7'],s['native_valid'],s['source_metadata'])
            self.assertEqual(list(c.root.glob('*.pt')),[])

class ReplayContracts(unittest.TestCase):
    def test_noise_close_to_contrast_is_flagged(self):
        class NearNoise:
            def __init__(self):self.i=0
            def ba(self,*args):
                v=(0.,1.,.75)[self.i];self.i+=1
                return torch.tensor([[v]]),torch.tensor([[v]]),torch.zeros((1,1,4))
        result,_=replay(snapshot(),NearNoise())
        self.assertTrue(result['contrasts']['dx']['numeric_uncertainty'])
    def test_initialization_or_unmarked_snapshot_not_replayed(self):
        for phase in (None,'INITIALIZATION','TRAJECTORY_FILLER'):
            s=snapshot();s['phase']=phase
            with self.subTest(phase=phase),self.assertRaises(ValueError):replay(s,SyntheticCandidate())
    def test_three_independent_branches_same_inputs_RNG_and_no_trajectory_score(self):
        s=snapshot();candidate=SyntheticCandidate();before=argument_manifest(s['args'])
        result,states=replay(s,candidate)
        self.assertEqual(len(candidate.initial),3)
        self.assertTrue(all(x==before for x in candidate.initial))
        self.assertEqual(result['contrasts']['dx']['A5_A5_l2'],0.)
        self.assertGreater(result['contrasts']['disps']['A5_A7_l2'],0.)
        self.assertFalse(result['ATE_RPE_computed']);self.assertFalse(result['complete_trajectory'])
        self.assertEqual(argument_manifest(s['args']),before)
    def test_native_U_updates_allowed_inside_branches_not_shared_initial_state(self):
        s=snapshot();result,states=replay(s,SyntheticCandidate())
        self.assertTrue(torch.equal(states['A5_first']['U'],states['A5_repeat']['U']))
        self.assertFalse(torch.equal(states['A5_first']['U'],states['A7']['U']))
        self.assertTrue(torch.all(s['args'][6]==0))
    def test_mutated_snapshot_rejected(self):
        s=snapshot();s['args'][1].add_(1)
        with self.assertRaises(ValueError):replay(s,SyntheticCandidate())
    def test_bad_uniform_strength_rejected(self):
        s=snapshot();s['a7'][0,0,0]=.99
        with self.assertRaises(ValueError):replay(s,SyntheticCandidate())
    def test_calls_are_nested_not_independent_clusters(self):
        result,_=replay(snapshot(),SyntheticCandidate())
        x=fsr_sequence_summary([result]*12)
        self.assertEqual(len(x),1);self.assertEqual(x[0]['independent_sequence_clusters'],1)
        self.assertEqual(x[0]['nested_BA_calls'],12)

class StatisticsContracts(unittest.TestCase):
    def test_constant_estimate_retains_raw_scale_error_without_fake_ATE(self):
        from score_completed_runs import score_trajectory
        gt=np.repeat(np.eye(4)[None],64,axis=0);gt[:,0,3]=np.linspace(0,10,64)
        pred=np.zeros((64,7));pred[:,6]=1
        m,rows=score_trajectory(pred,gt,np.arange(1,65))
        self.assertEqual(m['raw_path_ratio_abs_error'],1.);self.assertIsNone(m['ate_sim3_path_pct'])
        self.assertTrue(all(r['alignment']=='raw' for r in rows))
    def test_scorer_global_Sim3_corrects_rotations_and_uses_GT_path(self):
        from score_completed_runs import score_trajectory
        from scipy.spatial.transform import Rotation
        t=np.linspace(0,3,64);gt=np.repeat(np.eye(4)[None],64,axis=0)
        gt[:,:3,3]=np.c_[t,np.sin(t),np.cos(.4*t)];gt[:,:3,:3]=Rotation.from_euler('z',t*.1).as_matrix()
        q=Rotation.from_euler('xyz',[.3,.5,.7]).as_matrix();s=2.3;shift=np.array([1,2,3])
        p=((gt[:,:3,3]-shift)@q)/s;r=q.T@gt[:,:3,:3]
        pred=np.c_[p,Rotation.from_matrix(r).as_quat()]
        m,pairs=score_trajectory(pred,gt,np.arange(1,65))
        self.assertLess(m['ate_sim3_path_pct'],1e-10)
        self.assertGreater(m['raw_path_ratio_abs_error'],.1)
        self.assertLess(m['single_global_sim3_RPE_rotation_deg'],1e-9)
    def rows(self):
        rows=[]
        for i in range(19):
            for seed in (43,44,45):
                for arm in ('A0','A1','A4','A5','A7'):
                    rows.append(dict(sequence=f'synthetic_{i:03}',seed=seed,arm=arm,status='COMPLETE',initialized=True,
                                     ate_sim3_path_pct=1+i*.1+(.2 if arm=='A7' else 0),synthetic=True))
        return rows
    def test_plan_has_285_unique_jobs_57_per_arm(self):
        plan=validate_plan();self.assertEqual(len(plan),285)
        for arm in ('A0','A1','A4','A5','A7'):self.assertEqual(sum(r['arm']==arm for r in plan),57)
    def test_source_cluster_not_seed_pseudoreplication(self):
        r=paired_bootstrap(self.rows());self.assertEqual(r['independent_clusters'],19)
        np.testing.assert_allclose(r['CI95'],[-.2,-.2],atol=1e-12)
    def test_failed_and_unscorable_outcomes_not_zero_imputed(self):
        rows=self.rows()
        for r in rows:
            if r['sequence']=='synthetic_000' and ((r['seed']==45 and r['arm']=='A7')or(r['seed']==44 and r['arm']=='A5')):
                r['ate_sim3_path_pct']=None
        paired=paired_bootstrap(rows);strict=paired_bootstrap(rows,strict=True)
        self.assertEqual(paired['sequence_pairs'][0]['common_seeds'],[43])
        self.assertEqual(strict['independent_clusters'],18)
    def test_failure_denominator_includes_missing_runs(self):
        rows=self.rows();plan=[dict(sequence=r['sequence'],seed=r['seed'],arm=r['arm']) for r in rows]
        rows=[r for r in rows if r['arm']!='A7']
        accounting=failure_accounting(plan,rows);r=next(x for x in accounting if x['arm']=='A7')
        self.assertEqual(r['planned'],57);self.assertEqual(r['missing'],57);self.assertEqual(r['ATE_scorable'],0)
    def test_duplicate_outcome_is_rejected(self):
        rows=self.rows();plan=[dict(sequence=r['sequence'],seed=r['seed'],arm=r['arm']) for r in rows]
        with self.assertRaises(ValueError):failure_accounting(plan,rows+[rows[0]])
    def test_single_cluster_is_not_given_fake_CI(self):
        rows=[r for r in self.rows() if r['sequence']=='synthetic_000']
        self.assertIsNone(paired_bootstrap(rows)['CI95'])
    def test_bootstrap_reproducible_with_preregistered_seed(self):
        self.assertEqual(paired_bootstrap(self.rows()),paired_bootstrap(self.rows()))

class AdmissionAndGuards(unittest.TestCase):
    def test_authorized_job_cannot_be_relabelled_to_another_arm(self):
        from authorization import verify_requested_job
        row=validate_plan()[0]
        verify_requested_job('END_TO_END',row['job_key'],row['window'],row['arm'],int(row['seed']))
        other='A7' if row['arm']!='A7' else 'A5'
        with self.assertRaises(PermissionError):verify_requested_job('END_TO_END',row['job_key'],row['window'],other,int(row['seed']))
    def test_cache_job_is_bound_to_a_frozen_window(self):
        from authorization import verify_requested_job
        window=validate_plan()[0]['window']
        verify_requested_job('PRIOR_CACHE','cache_'+window,window)
        with self.assertRaises(PermissionError):verify_requested_job('PRIOR_CACHE','cache_'+window,'unapproved_window')
    def test_E2E_CPU_driver_and_attempt_no_retry(self):
        import run_end_to_end as runner
        job=dict(sequence='SYNTHETIC',environment='Day',seed=43,arm='A0',job_key='SYNTHETIC_TEST_JOB')
        with tempfile.TemporaryDirectory(dir='D:/aaa/tmp/gamecam-vo') as tmp,patch.object(runner,'TASK',Path(tmp)),patch.object(runner,'require_approved_runtime',return_value={}):
            r=runner.execute_job(job,None,driver=lambda j,o:dict(status='COMPLETE',initialized=True,synthetic=True))
            self.assertTrue(r['synthetic'])
            with self.assertRaises(FileExistsError):runner.execute_job(job,None,driver=lambda j,o:dict(status='COMPLETE'))
    def test_engineering_failure_initialization_not_falsely_inferred(self):
        plan=[dict(sequence='s',seed=43,arm='A5')]
        x=failure_accounting(plan,[dict(sequence='s',seed=43,arm='A5',status='ENGINEERING_FAILURE',initialized=None)])
        r=next(r for r in x if r['arm']=='A5')
        self.assertEqual(r['initialization_unknown'],1);self.assertEqual(r['initialization_failed'],0)
    def test_no_current_execution_authority(self):
        with self.assertRaises(PermissionError):require_approved_runtime(None,'END_TO_END','any')
    def test_incomplete_or_test_authorization_rejected(self):
        with tempfile.TemporaryDirectory(dir='D:/aaa/tmp/gamecam-vo') as tmp:
            p=Path(tmp)/'approval.json';p.write_text(json.dumps(dict(approved=True,test_only=True)))
            with self.assertRaises(PermissionError):require_approved_runtime(p,'END_TO_END','any')
    def test_GPU_facing_windows_have_no_GT_paths(self):
        windows=json.loads((TASK/'configs/GPU_RGB_INPUTS.json').read_text())['windows']
        self.assertEqual(len(windows),19)
        for w in windows:
            self.assertFalse(any('gt' in k.lower() for k in w))
            self.assertTrue(w['historical_full_sequence_baseline_exposure']);self.assertFalse(w['blind_validation'])
    def test_selected_sources_exclude_B_and_val014(self):
        selected=list(csv.DictReader((TASK/'data/SELECTED_19_WINDOWS.csv').open()))
        old=list(csv.DictReader((TASK.parent/'TASK011B/configs/VIPER_WINDOW_MANIFEST.csv').open()))
        self.assertFalse({r['sequence'] for r in selected}&{r['sequence'] for r in old})
        self.assertNotIn('val_014',{r['sequence'] for r in selected})
    def test_formal_driver_refuses_before_torch_or_native_import(self):
        for name in ('native_driver.py','cache_priors.py'):
            code="import runpy,sys\ntry:runpy.run_path("+repr(str(TASK/name))+",run_name='__main__')\nexcept PermissionError:pass\nelse:raise AssertionError('missing gate')\nassert 'torch' not in sys.modules\nprint('GATED_BEFORE_MODEL_IMPORT')"
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='-1')
            p=subprocess.run([sys.executable,'-B','-c',code],cwd=TASK,capture_output=True,text=True,env=env)
            self.assertEqual(p.returncode,0,p.stderr)
    def test_all_frozen_configs_match_their_SHA(self):
        p=json.loads((TASK/'configs/FROZEN_EXPERIMENT_PROTOCOL.json').read_text())
        for r in p['files']:
            self.assertEqual(hashlib.sha256((TASK/r['path']).read_bytes()).hexdigest(),r['sha256'])

if __name__=='__main__':unittest.main(verbosity=2)
