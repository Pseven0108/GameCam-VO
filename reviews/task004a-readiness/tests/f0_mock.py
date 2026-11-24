"""Extract only named methods from the frozen files; never import their modules."""
import ast
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

from contracts import ROOT, need, read_json, stat_sha


def methods(path, owner, *names):
    tree = ast.parse(path.read_bytes(), filename=str(path))
    class_node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
    selected = {n.name:n for n in class_node.body if isinstance(n, ast.FunctionDef) and n.name in names}
    need(selected.keys() == set(names), 'required frozen methods missing')
    for item in selected.values():
        item.decorator_list = []
    return list(selected.values())


def build(owner, base, methods_to_copy, env):
    node = ast.parse(f'class {owner}({base}):\n    pass')
    node.body[0].body = methods_to_copy
    exec(compile(ast.fix_missing_locations(node), f'<cpu-f0-{owner}>', 'exec'), env)
    return env[owner]


def exercise(final_phases):
    candidates = ROOT/'assets/candidates'
    runner = candidates/'task004_run_segment.py'
    slam_py = candidates/'preview/src/slam.py'
    identity = read_json(ROOT/'assets/evidence/SOURCE_AND_CANDIDATE_IDENTITY.json')
    src = Path(identity['source_path'])/'src/backend.py'
    need(stat_sha(src) == identity['verified_source_blobs']['src/backend.py']['sha256'], 'backend identity changed')
    events, indexes = [], []

    class RGBNoPose:
        pass

    class FakeIndices(list):
        def __getitem__(self, i):
            v = super().__getitem__(i)
            return FakeIndices(v) if isinstance(i,slice) else v

        def cpu(self):
            return self

        def int(self):
            return self

        def tolist(self):
            return list(self)

    class Stream(RGBNoPose):
        out = Path('MOCK_NOT_WRITTEN')
        seen = 487
        peak = 4
        ids = list(range(1, 488))

        def __len__(self):
            return self.seen

    class Video:
        counter = SimpleNamespace(value=4)
        timestamp = FakeIndices([0,311,327,486])
        metric_depth_reg = True

        def save_video(self, path):
            events.append(('save_video', self.metric_depth_reg, self.counter.value, path))

    class Filler:
        def setup_feature_extractor(self):
            events.append(('setup_feature_extractor',))

    def fill(filler, mapper, stream, *, fast_mode):
        need(isinstance(filler,Filler) and mapper is None and fast_mode is True, 'changed Filler call interface')
        events.append(('fill', obj.video.metric_depth_reg, len(stream)))
        return [None] * len(stream)

    def export(trajectory, stream, printer, logger, destination, name):
        need(len(trajectory) == len(stream) == 487 and name == 'full_traj', 'changed export call interface')
        events.append(('export', len(trajectory), destination))

    def dump(path, doc):
        need(path.name == 'keyframes.json', 'unexpected output path')
        indexes.append(doc)
        events.append(('keyframe_index', doc['final_count']))

    env = dict(RGB_NoPose=RGBNoPose, full_traj_fill=fill, full_traj_eval=export, dump=dump, BUFFER=500,
               timer=SimpleNamespace(section=lambda _:nullcontext(), _report_summary=lambda _:events.append(('timer_summary',))),
               progress=lambda _out, phase, **_kwargs:events.append(('progress',phase)),
               task003=lambda:SimpleNamespace(boundary=lambda stage,video:events.append((stage,video.metric_depth_reg))),
               task004_policy=lambda:SimpleNamespace(final_phases=final_phases),
               FontColor=SimpleNamespace(TRACKER='tracker',EVAL='eval'),
               torch=SimpleNamespace(cuda=SimpleNamespace(empty_cache=lambda:events.append(('empty_cache_STUB',)))))
    frozen_backend = build('FrozenInitBackend', 'object', methods(src, 'Backend', '__init__'), env)

    class Backend(frozen_backend):
        def __init__(self, net, video, cfg):
            super().__init__(net, video, cfg)
            events.append(('construct_backend', video.metric_depth_reg))

        def dense_ba(self, steps, **_):
            events.append(('dense_ba_STUB', steps, self.video.metric_depth_reg))

    env['Backend'] = Backend
    build('BaseSlam', 'object', methods(slam_py, 'SLAM', 'backend','terminate'), env)
    obs = build('ObservedSlam', 'BaseSlam', methods(runner, 'ObservedSLAM', 'backend','terminate'), env)
    obj = obs()
    import yaml
    obj.cfg = yaml.safe_load((candidates/'r2_sealed_config.yaml').read_bytes())
    obj.save_dir, obj.stream, obj.video, obj.traj_filler = 'MOCK_NOT_WRITTEN/native', Stream(), Video(), Filler()
    obj.printer, obj.logger = SimpleNamespace(print=lambda *args:None), object()
    obj.droid_net = SimpleNamespace(update=object())
    obj.tracker = SimpleNamespace(frontend=SimpleNamespace(is_initialized=True))
    obj.final_clean = False
    obj.ba = Backend(obj.droid_net,obj.video,obj.cfg)
    original_ba = obj.ba
    need(original_ba.t0 == original_ba.t1 == 0 and original_ba.video is obj.video, 'Backend constructor contract drift')
    events.clear()
    obj.terminate()
    need(obj.final_clean is True and obj.video.metric_depth_reg is True, 'termination state not restored')
    need(len(indexes) == 1 and indexes[0]['rgb_ids'] == [1, 312, 328, 487], 'keyframe index provenance failed')
    need([e[0] for e in events if e[0] in ('keyframe_index','save_video','setup_feature_extractor','fill','export')]
         == ['keyframe_index','save_video','setup_feature_extractor','fill','export'], 'exit output order failed')
    need(('fill',True,487) in events and ('save_video',True,4,'MOCK_NOT_WRITTEN/native/video.npz') in events,
         'Filler or video export received an unexpected prior flag/state')
    dense = [e[1:] for e in events if e[0] == 'dense_ba_STUB']
    need(dense == ([] if final_phases == 0 else [(7,False),(12,False)]), 'Final BA branch mismatch')
    need((obj.ba is original_ba) == (final_phases == 0), 'unexpected Backend reconstruction result')
    if final_phases == 0:
        need(('final_ba_skipped',True) in events and not any(e[0] == 'empty_cache_STUB' for e in events), 'F0 side effect drift')
    return dict(mode='CPU_F0_MOCK_ONLY', final_phases=final_phases, events=events, keyframe_index=indexes[0],
                actual_backend_outputs_verified=False, sources=dict(backend=str(src), slam=str(slam_py), runner=str(runner)))
