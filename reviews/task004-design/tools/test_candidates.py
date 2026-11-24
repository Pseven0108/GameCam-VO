"""Exercise selected candidate methods with CPU doubles; no DROID or torch imports."""

import ast
import contextlib
import csv
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import numpy as np

from prepare_candidates import ROOT, SOURCE, control, digest, load

PREVIEW = ROOT / 'candidates/preview'
RUNNER = ROOT / 'candidates/task004_run_segment.py'
sys.path.insert(0, str(PREVIEW))
from task003_observer import Recorder, geometry


def member(path, cls, name):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    c, = (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    f, = (n for n in c.body if isinstance(n, ast.FunctionDef) and n.name == name)
    f.decorator_list = []
    return f


def synthetic_class(label, base, nodes, env):
    template = ast.parse(f'class {label}(_base):\n    pass\n')
    template.body[0].body = list(nodes)
    scope = dict(_base=base, **env)
    exec(compile(ast.fix_missing_locations(template), '<CPU mock candidate methods>', 'exec'), scope)
    return scope[label]


class Tensor(np.ndarray):
    def __new__(cls, value):
        return np.asarray(value).view(cls)

    def view(self, *shape):
        return self.reshape(*shape)

    def permute(self, *order):
        return self.transpose(order)

    def contiguous(self):
        return Tensor(np.ascontiguousarray(self))

    def clamp(self, lo, hi):
        return self.clip(lo, hi)

    def clamp_(self, min):
        self[:] = np.maximum(self, min)

    def to(self, dtype):
        return self.astype(dtype)

    def clone(self):
        return self.copy()


class GeometryCalls:
    def __init__(self, directory):
        self.record = Recorder(directory / 'mock_observer.jsonl')
        self.native = []
        self.fail = False
        self.events = []
        self.record.emit = lambda name, start, **data: self.events.append((name, data))
        self.torch = NS(amp=NS(autocast=lambda *a, **k: contextlib.nullcontext()),
                        cat=lambda arrays, dim: Tensor(np.concatenate(arrays, axis=dim)),
                        unique=lambda x: np.unique(x), float=np.float32, log=np.log, exp=np.exp,
                        isnan=np.isnan, isinf=np.isinf, cuda=NS(empty_cache=lambda: None))
        common = dict(torch=self.torch, task003=lambda: self.record, SummaryWriter=object,
                      task004_local_flags=control.local_flags, droid_backends=NS(ba=self.fake_native))
        self.Video = synthetic_class('DepthVideo', object, [self.method('depth_video.py','DepthVideo','ba')], common)
        self.Graph = synthetic_class('FactorGraph', object, [self.method('factor_graph.py','FactorGraph','update')], common)
        self.Frontend = synthetic_class('Frontend', object, [self.method('frontend.py','Frontend',n)
                                for n in ('__call__', '__update')], common)

    @staticmethod
    def method(file, cls, name):
        return member(PREVIEW / 'src' / file, cls, name)

    def fake_native(self, *args):
        self.native.append((args, self.record.stage, self.record.ba_id))
        if self.fail:
            raise RuntimeError('synthetic native failure')
        # Toy changes to exercise observation; this is not a solver or a model.
        args[1][0, 1, 1] = -0.25
        if args[25]:
            args[6][0, 0, 0] += 0.125

    def make(self, distance=5):
        v = self.Video()
        v.ht, v.wd, v.down_scale = 64, 64, 8
        v.cfg = {'tracking': {'frontend': {'enable_loop': False}, 'uncertainty_params': {
            'gamma_data': 0.1, 'gamma_prior': 0.05, 'gamma_depth': 0.01,'lr': 0.1, 'weight_decay': 0.002}}}
        v.metric_depth_reg = v.uncertainty_aware = v.enable_affine_transform = True
        v.enable_bidirectional_uncer = v.debug = False
        v.counter, v.get_lock = NS(value=3), contextlib.nullcontext
        v.timestamp = Tensor([0, 1, 2, 3, 4])
        v.poses = Tensor(np.tile([0.,0.,0.,0.,0.,0.,1.], (5, 1)))
        v.disps = Tensor(np.ones((5,8,8), dtype=np.float32))
        v.mono_disps, v.zeros = 2 * v.disps.copy(), 0 * v.disps.copy()
        v.mono_disps[1,0,0] = 0
        v.intrinsics = Tensor([[3.,3.,3.,3.]])
        v.uncertainties = v.disps.copy()
        v.temp_y_cdot = v.zeros.copy()
        v.affine_weights = Tensor([0.,-1.])
        v.dino_feats_resize = Tensor(np.zeros((5,1,8,8)))
        v.dino_feats = Tensor(np.zeros((5,1,2,2)))
        grid = Tensor(np.zeros((1,2,8,8,2)))
        v.reproject = lambda *a: (grid, None)
        v.upsample = v.set_dirty = v.update_valid_depth_mask = lambda *a: None
        v.distance = lambda *a, **kw: Tensor(distance)
        g = self.Graph()
        g.video, g.corr = v, lambda coords: None
        g.ii, g.jj = Tensor([0, 1]), Tensor([1, 2])
        g.ii_inac, g.jj_inac = Tensor(np.array([], dtype=int)), Tensor(np.array([], dtype=int))
        g.target_inac = g.weight_inac = grid[:, :0]
        g.target, g.weight, g.coords0 = grid, grid+1, Tensor(grid[0,0])
        g.age, g.damping = Tensor([0,0]), Tensor(np.ones((5,8,8)))
        g.net = g.inp = None
        g.update_op = lambda *a: (None, grid, grid+1, Tensor(np.ones((2, 8, 8))), None)
        g.rm_factors = g.add_proximity_factors = lambda *a, **kw: None
        g.rm_keyframe = lambda *a: None
        f = self.Frontend()
        f.video, f.graph = v, g
        f.t1, f.warmup, f.is_initialized = 2, 12, True
        f.iters1, f.iters2, f.max_age, f.beta = 3, 2, 50, .75
        f.frontend_radius = f.frontend_nms = f.frontend_thresh = 1
        f.frontend_window, f.enable_loop, f.enable_opt_dyn_mask = 25, False, True
        f.max_consecutive_drop_of_keyframes, f.num_keyframes_dropped, f.keyframe_thresh = 5, 0, 3
        return v, g, f


@contextlib.contextmanager
def selected(arm):
    p = (ROOT / 'policies' / f'{arm}.json').resolve()
    with patch.dict(os.environ, GAMECAM_TASK004_POLICY=str(p), GAMECAM_TASK004_POLICY_SHA256=digest(p)):
        control.policy.cache_clear()
        try:
            yield
        finally:
            control.policy.cache_clear()


class CandidateTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory(dir=ROOT, prefix='mock-')
        self.addCleanup(td.cleanup)
        self.mock = GeometryCalls(Path(td.name))

    def test_policy_covers_all_eight_orthogonal_factor_cells(self):
        with (ROOT / 'TASK004_FACTORIAL_MATRIX.csv').open(newline='') as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 8)
        self.assertEqual({int(r['screening_slot']) for r in rows}, set(range(1, 9)))
        design = []
        for r in rows:
            self.assertEqual(digest(ROOT / r['policy_file']), r['policy_sha256'])
            with selected(r['arm']):
                d,w,u = (2*x-1 for x in control.policy().local_dwu)
                design.append([1,d,w,u,d*w,d*u,w*u,d*w*u])
        a = np.asarray(design)
        np.testing.assert_array_equal(a.T@a, np.eye(8)*8)

    def test_phase_policies_reject_mislabeled_cell_and_scope(self):
        wrong = load(ROOT / 'policies/E4.json')
        wrong['local_dwu'] = [0,0,0]
        with self.assertRaisesRegex(ValueError, 'Invalid Task 004 arm'):
            control.parse_policy(wrong)
        wrong = load(ROOT / 'policies/E1.json'); wrong['final_phases'] = 1
        with self.assertRaises(ValueError):
            control.parse_policy(wrong)
        with selected('E4'), patch.dict(os.environ, GAMECAM_TASK004_POLICY_SHA256='0'*64):
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                control.policy()

    def test_native_signature_all_cells_in_both_local_stages(self):
        for arm, expected in control.FACTORIAL.items():
            for phase in sorted(control.LOCAL_PHASES):
                with self.subTest(arm=arm, phase=phase), selected(arm):
                    v,g,_ = self.mock.make()
                    self.mock.record.context(phase, 1)
                    g.update(use_inactive=True, task004_phase=phase)
                    args, logged, call_id = self.mock.native[-1]
                    self.assertEqual((args[3] is v.mono_disps, args[26], args[25]), expected)
                    self.assertIs(args[3], v.mono_disps if expected[0] else v.zeros)
                    self.assertIs(args[6], v.uncertainties)
                    self.assertIs(args[8], v.dino_feats_resize)
                    self.assertIs(args[9], v.affine_weights)
                    self.assertEqual((args[15],args[20],args[23],args[28]), (2,.01,False,False))
                    before, native, clamp = self.mock.events[-3:]
                    self.assertEqual([n for n,_ in (before,native,clamp)], ['ba_before','ba_after_native','ba_after_clamp'])
                    self.assertEqual([r['ba_id'] for _,r in (before,native,clamp)], [call_id]*3)
                    self.assertEqual((logged,before[1]['task004_local_phase']), (phase,phase))
                    self.assertEqual([before[1][k] for k in ('metric_depth_prior_selected','source_uba','update_u')],list(expected))
                    self.assertEqual(before[1]['metric_depth_positive_support'], 191 if expected[0] else 0)
                    self.assertTrue(v.metric_depth_reg)
                    self.assertEqual(v.mono_disps[0,0,0], 2.0)
        self.assertEqual(len(self.mock.native), 16)

    def test_e0_matches_frozen_native_args_and_clamp(self):
        v,g,_ = self.mock.make()
        self.mock.record.context('frontend_local_predecision', 1)
        with selected('E0'):
            g.update(use_inactive=True, task004_phase='frontend_local_predecision')
        new = self.mock.native[-1][0]
        frozen = synthetic_class('FrozenDepthVideo',object,[member(SOURCE/'src/depth_video.py','DepthVideo','ba')],
            dict(torch=self.mock.torch,droid_backends=NS(ba=self.mock.fake_native)))
        base,_,_ = self.mock.make()
        old = frozen(); old.__dict__.update(base.__dict__)
        frozen.ba(old, Tensor(g.target), Tensor(g.weight), Tensor(new[10]), g.ii,g.jj, 1,3,
                  iters=2,lm=1e-4,ep=.1,lr=.1,weight_decay=.002,enable_update_uncer=True,enable_udba=True)
        old_args = self.mock.native[-1][0]
        self.assertEqual(len(new), len(old_args))
        for i,(a,b) in enumerate(zip(new,old_args)):
            np.testing.assert_array_equal(a,b,err_msg=f'native argument {i}')

    def test_nontarget_phase_bypasses_cell_including_filler(self):
        for name,d,w,u,pose_only in (
            ('frontend_init_neighborhood',1,0,1,0),('frontend_init_proximity',1,1,1,0),
            ('frontend_init_second',1,1,1,0),('online_global_ba',1,1,0,0),
            ('final_ba_phase_1',0,1,0,0),('final_ba_phase_2',0,1,0,0),('filler_pose_only',1,1,0,1)):
            with self.subTest(stage=name), selected('E8'):
                v,g,_ = self.mock.make()
                v.metric_depth_reg=bool(d)
                self.mock.record.context(name,2)
                g.update(use_inactive=True, motion_only=bool(pose_only), enable_udba=bool(w), enable_update_uncer=bool(u))
                native = self.mock.native[-1][0]
                self.assertEqual((native[3] is v.mono_disps,native[26],native[25],native[23]),(d,w,u,pose_only))
                before=self.mock.events[-3][1]
                self.assertIsNone(before['task004_local_phase'])
                self.assertEqual(before['metric_depth_branch_active'], bool(d and not pose_only))

    def test_rejected_keyframe_still_runs_three_predecision_calls(self):
        v,g,f = self.mock.make(distance=1)
        with selected('E4'):
            f(False,None)
        self.assertEqual([phase for _,phase,_ in self.mock.native], ['frontend_local_predecision']*3)
        self.assertEqual(v.counter.value,2)
        flags = [(a[3] is v.mono_disps,a[26],a[25]) for a,_,_ in self.mock.native]
        self.assertEqual(flags,[(0,0,1)]*3)

    def test_retained_keyframe_runs_both_local_stages(self):
        v,g,f = self.mock.make(distance=5)
        with selected('E6'):
            f(False,None)
        self.assertEqual([phase for _,phase,_ in self.mock.native],
                         ['frontend_local_predecision']*3 + ['frontend_local_retained']*2)
        self.assertEqual([call_id for _,_,call_id in self.mock.native], list(range(1,6)))
        self.assertEqual(v.counter.value,3)

    def test_no_candidate_no_ba_and_scope_mismatch_fails_closed(self):
        v,g,f = self.mock.make()
        f.t1 = v.counter.value
        with selected('E4'):
            f(False,None)
            self.assertEqual(self.mock.record.ba_id,0)
            self.mock.record.context('frontend_init_neighborhood')
            with self.assertRaisesRegex(ValueError,'scope mismatch'):
                g.update(task004_phase='frontend_local_predecision')
            self.mock.record.context('frontend_local_predecision')
            with self.assertRaisesRegex(ValueError,'missing its explicit'):
                g.update()
            self.assertEqual(len(self.mock.native),0)
            self.assertFalse(self.mock.events)

    def test_failed_native_call_is_not_logged_as_returned(self):
        v,g,_ = self.mock.make()
        self.mock.record.context('frontend_local_predecision')
        self.mock.fail = True
        with selected('E4'), self.assertRaisesRegex(RuntimeError,'synthetic native failure'):
            g.update(task004_phase='frontend_local_predecision')
        self.assertEqual([name for name,_ in self.mock.events],['ba_before'])
        self.assertEqual(len(self.mock.native),1)

    def test_raw_and_clamped_disparity_use_same_full_grid_not_sample(self):
        v,g,_ = self.mock.make()
        self.mock.record.context('frontend_local_predecision')
        with selected('E0'):
            g.update(task004_phase='frontend_local_predecision')
        _,after,clamp = self.mock.events[-3:]
        raw,post = (r['full_disparity_grid'] for _,r in (after,clamp))
        self.assertEqual((raw['total'],raw['negative'],post['negative'],post['float32_floor_count']), (192,1,0,1))
        self.assertEqual((after[1]['disparity']['n'],after[1]['disparity']['negative']),(12,0))

    def test_source_weight_diagnostic_has_known_reference_values(self):
        k = np.array([4.,4.,0.,0.]); p = np.array([[0.,0.,0.,0.,0.,0.,1.]]*2)
        d = np.ones((2,1,1)); u = d.copy(); e = np.array([0]); j = np.array([1]); t=np.zeros((1,1,1,2))
        for enabled,expected in ((True,.0001),(False,.001)):
            x = geometry(k,p,d,u,e,j,t,np.ones_like(t),enabled,False)
            self.assertEqual(x['valid_projection_samples'],1)
            self.assertAlmostEqual(x['effective_weight']['median'],expected)
            self.assertEqual(x['weighted_residual_sse'],0)
        zero = geometry(k,p,d,u,e,j,t,np.zeros_like(t),True,False)
        self.assertEqual(zero['zero_weight_valid_projection_samples'],1)
        self.assertEqual(zero['positive_weight_observation_samples'],0)
        invalid = geometry(k,p,d,u,e,j,t,np.array([[[[-1.,1.]]]]),True,False)
        self.assertEqual(invalid['invalid_weight_valid_projection_samples'],1)
        self.assertEqual(invalid['positive_weight_observation_samples'],0)

    def test_cached_prior_is_visible_but_not_selected_when_d_is_off(self):
        v,g,_ = self.mock.make()
        self.mock.record.context('frontend_local_predecision')
        with selected('E1'):
            g.update(task004_phase='frontend_local_predecision')
        before = self.mock.events[-3][1]
        self.assertEqual(before['cached_prior_total'],192)
        self.assertEqual(before['cached_prior_positive_support'],191)
        self.assertEqual(before['metric_depth_positive_support'],0)
        self.assertEqual(before['prior_support'],[])
        self.assertEqual(int(np.count_nonzero(v.mono_disps)),319)

    def test_green_path_scope_preserves_non_target_source_statements(self):
        class StripObserver(ast.NodeTransformer):
            def visit_Expr(self,n):
                c=n.value
                if (isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute) and isinstance(c.func.value,ast.Call)
                        and isinstance(c.func.value.func,ast.Name) and c.func.value.func.id=='task003'):
                    return None
                return self.generic_visit(n)

            def visit_Call(self,n):
                n.keywords=[k for k in n.keywords if k.arg!='task004_phase']
                return self.generic_visit(n)

        for n in ('__initialize','initialize_second_stage','__call__','__update'):
            f = SOURCE/'src/frontend.py'; p=PREVIEW/'src/frontend.py'
            self.assertEqual(ast.dump(member(f,'Frontend',n)), ast.dump(StripObserver().visit(member(p,'Frontend',n))))
        for file,cls,n in (('slam.py','SLAM','terminate'),('trajectory_filler.py','PoseTrajectoryFiller','__fill')):
            self.assertEqual(ast.dump(member(SOURCE/'src'/file,cls,n)),
                             ast.dump(StripObserver().visit(member(PREVIEW/'src'/file,cls,n))))

    def test_final_diagnostic_three_arms_preserve_filler_and_export(self):
        for arm, expected in (('F0', []), ('F1',[7]), ('F2',[7,12]), ('E0',[7,12])):
            with self.subTest(arm=arm), selected(arm):
                events=[]
                native = NS(dense_ba=lambda steps,**kw: events.append(('dense',steps,self.slam.video.metric_depth_reg,kw)))
                printer=NS(print=lambda *a: None)
                v=NS(counter=NS(value=3), metric_depth_reg=True,save_video=lambda p: events.append(('video',)))
                env=dict(task003=lambda:NS(boundary=lambda n,v: events.append(('stage',n))),
                         task004_policy=control.policy,Backend=lambda *a:native,torch=self.mock.torch,
                         FontColor=NS(TRACKER=None,EVAL=None),progress=lambda out,phase,**kw:events.append(('progress',phase)),
                         timer=NS(section=lambda *a:contextlib.nullcontext(),_report_summary=lambda *a:None),
                         full_traj_eval=lambda *a:events.append(('export',)))
                base_stream=type('RGB_NoPose',(object,),{'__len__':lambda self:487})
                stream = synthetic_class('ViperRGB',base_stream,[member(RUNNER,'ViperRGB','task004_begin_filler')],env)()
                stream.phase=None; stream.seen=487; stream.fill_seen=0; stream.out='mock'; stream.video=v
                def fill(filler, mapper, stream, fast_mode):
                    self.assertTrue(fast_mode); self.assertIsNone(mapper)
                    stream.task004_begin_filler()
                    self.assertEqual(stream.phase,'filler')
                    stream.fill_seen = 487
                    events.append(('filler',))
                    return 'mock trajectory'
                env.update(full_traj_fill=fill,RGB_NoPose=base_stream)
                cls=synthetic_class('SLAM',object,[member(PREVIEW/'src/slam.py','SLAM',n) for n in ('backend','terminate')],env)
                s=synthetic_class('ObservedSLAM',cls,[member(RUNNER,'ObservedSLAM','backend')],env)()
                self.slam=s
                s.stream,s.video,s.printer,s.droid_net,s.logger,s.save_dir=stream,v,printer,None,None,'mock'
                s.cfg={'tracking':{'backend':{'final_ba':True},'frontend':{'enable_opt_dyn_mask':True}},
                       'mapping':{'enable':False,'eval_before_final_ba':False}}
                s.traj_filler=NS(setup_feature_extractor=lambda:None)
                s.terminate()
                dense=[e for e in events if e[0]=='dense']
                self.assertEqual([e[1] for e in dense],expected)
                self.assertTrue(all(not e[2] and e[3]['enable_udba'] for e in dense))
                self.assertEqual([e[0] for e in events if e[0] in ('video','filler','export')],['video','filler','export'])
                self.assertTrue(v.metric_depth_reg and s.final_clean and stream.fill_seen==487)
                with self.assertRaisesRegex(ValueError,'unexpected Filler entry'):
                    stream.task004_begin_filler()

    def test_native_filler_marks_phase_before_beginning_rgb_iteration(self):
        fn = member(PREVIEW/'src/trajectory_filler.py','PoseTrajectoryFiller','__call__')
        track=[]
        def fake_fill(self, timestamps, *args):
            track.append(('fill',tuple(timestamps)))
            return [0]
        filler=synthetic_class('PoseTrajectoryFiller',object,[fn],dict(
            BaseDataset=object, FontColor=NS(INFO=None), tqdm=lambda x:x,
            lietorch=NS(cat=lambda xs,dim:xs)))()
        filler._PoseTrajectoryFiller__fill=fake_fill.__get__(filler)
        filler.uncertainty_aware=False
        filler.printer=NS(print=lambda *a:None)
        class Stream:
            def get_intrinsic(self): return 'fake K'
            def task004_begin_filler(self): track.append(('enter',))
            def __iter__(self):
                if track != [('enter',)]: raise AssertionError('Filler phase set too late')
                return iter((i,'fake image',None,None) for i in range(17))
        filler(Stream())
        self.assertEqual(track,[('enter',),('fill',tuple(range(16))),('fill',(16,))])

    def test_review_runner_exits_before_importing_any_model(self):
        run=subprocess.run([sys.executable,'-B',str(RUNNER)], capture_output=True,text=True,timeout=8)
        self.assertNotEqual(run.returncode,0)
        self.assertIn('GPU execution is not approved',run.stderr)
        self.assertNotIn('ModuleNotFoundError',run.stderr)


if __name__ == '__main__':
    print('CPU doubles only; no model, dataset, or torch imports', flush=True)
    unittest.main(verbosity=2)
