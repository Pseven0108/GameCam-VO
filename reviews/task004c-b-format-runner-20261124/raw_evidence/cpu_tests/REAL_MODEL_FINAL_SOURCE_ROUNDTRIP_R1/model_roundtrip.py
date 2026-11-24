"""Rebuild omitted CPU object metadata and reuse verified historical Tensor files."""
from collections import defaultdict
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import traceback
from types import SimpleNamespace

import cpu_model_fixture as fixture
import numpy as np
import torch
import yaml
from checkpoint.rng_state import capture_rng_state, restore_rng_state
from control_common import ControlError, canonical, digest, file_sha, require_space
from native_control.configdict_adapter import TAG
from native_control.snapshot import FORMAT, ObjectEncoder, byte_sha, load_state, read_manifest


OUT = Path(sys.argv[1]).resolve()
ROOT = fixture.ROOT
PRIOR = ROOT.parent / 'DROID_W_TASK004C_B_AUTONOMOUS_20261124_R1'
OLD_RUN = PRIOR / 'cpu_tests/closure_roundtrip_r2_rng_validation'
OLD = OLD_RUN / 'snapshot_evidence'
ARCHIVE_SHA = '1aa48a77cea13322ef250e3281b2d91278e3dbf2737ae501d6ac8c3f7a236ea0'
INPUT = '/root/rivermind-data/DROID_W_TASK003_VAL007_OBSERVATION_R1/inputs/val_007_full_00001-00487/INPUT.json'
BASE_CONFIG = '/root/rivermind-data/DROID_W_TASK004B_CONFIRMATORY_20261123T124144277Z/release/candidates/r2_sealed_config.yaml'
FLOOR = 10 * 1024**3
SNAPSHOT = OUT / 'corrected_cpu_snapshot'


def write_json(name, obj):
    with (OUT / name).open('x', encoding='utf-8') as file:
        json.dump(obj, file, indent=2, ensure_ascii=False)


class Sink:
    def __init__(self):
        import torch.multiprocessing as mp
        self.progress_counter = mp.get_context('spawn').Value('i', 0)

    def print(self, *args, **kwargs):
        pass

    def add_text(self, *args, **kwargs):
        pass


def storage_key(metadata):
    return tuple(metadata[field] for field in ('byte_size', 'raw_sha256', 'device', 'cpu_shared'))


def publish_cpu_fixture(root, graph, old):
    # Only this private test stage creates hard links. Neither the snapshot
    # reader nor the native GPU saver gets a route around file and SHA checks.
    old_by_content = defaultdict(list)
    for sid, metadata in old['storages'].items():
        old_by_content[storage_key(metadata)].append((sid, metadata))
    stage = OUT / 'cpu_snapshot_staging'
    stage.mkdir()
    files, storages, links = {}, {}, []
    for sid, storage in graph.storages.items():
        raw = storage['raw']
        name = sid + '.pt'
        metadata = {'file': name, 'byte_size': raw.numel(), 'raw_sha256': byte_sha(raw),
                    'device': storage['device'], 'cpu_shared': storage['shared'],
                    'encoding': 'TORCH_ZIP_GZIP_V1'}
        storages[sid] = metadata
        candidates = old_by_content[storage_key(metadata)]
        target = stage / name
        if candidates:
            _, original = candidates.pop()
            source = OLD / original['file']
            os.link(source, target)
            files[name] = old['files'][original['file']]
            assert target.samefile(source)
            links.append({'source': original['file'], 'target': name, **files[name]})
        else:
            # Worst-case bound for the small compressed CPU-only fixture
            # payload. Existing model files never enter this branch.
            require_space(stage, raw.numel() + raw.numel() // 500 + 65536, FLOOR)
            with target.open('xb') as file:
                with gzip.GzipFile(filename='', mode='wb', fileobj=file, compresslevel=1, mtime=0) as zipped:
                    torch.save(raw.clone(), zipped)
                file.flush()
                os.fsync(file.fileno())
            files[name] = {'bytes': target.stat().st_size, 'sha256': file_sha(target)}
    assert len(links) == len(old['storages']), 'Historical Tensor Storage reuse is incomplete'
    manifest = {
        'schema': FORMAT, 'endianness': sys.byteorder, 'root': root,
        'nodes': graph.nodes, 'classes': graph.classes, 'storages': storages, 'files': files,
        'provenance': {'artifact_kind': 'CPU_NATIVE_INTERFACE_FIXTURE',
                       'fixture': 'REAL_WEIGHTED_MODELS_WITH_CPU_TRACKER_STATE',
                       'historical_snapshot_sha256': ARCHIVE_SHA, 'source_pid': os.getpid()},
    }
    manifest['state_sha256'] = digest(manifest)
    raw_manifest = canonical(manifest)
    require_space(stage, len(raw_manifest) + 65536, FLOOR)
    (stage / 'manifest.json').write_bytes(raw_manifest)
    (stage / 'COMPLETE.json').write_bytes(canonical({'manifest_sha256': hashlib.sha256(raw_manifest).hexdigest()}))
    assert not SNAPSHOT.exists()
    stage.rename(SNAPSHOT)
    read_manifest(SNAPSHOT, manifest['state_sha256'])
    write_json('SNAPSHOT_REUSE.json', {
        'historical_state_sha256': ARCHIVE_SHA,
        'reused_files': len(links),
        'reused_compressed_bytes': sum(row['bytes'] for row in links),
        'new_storage_files': len(files) - len(links),
        'new_compressed_bytes': sum(x['bytes'] for x in files.values()) - sum(row['bytes'] for row in links),
        'metadata_bytes': len(raw_manifest),
        'unique_logical_storage_bytes': sum(x['byte_size'] for x in storages.values()),
        'cpu_shared_logical_bytes': sum(x['byte_size'] for x in storages.values() if x['cpu_shared']),
        'corrected_cpu_snapshot_sha256': manifest['state_sha256'],
        'links': links,
    })


def make_runtime(cfg, models, sink, counter, observer_file):
    from src.depth_video import DepthVideo
    from src.tracker import Tracker
    import src.motion_filter as mf
    from src.modules.droid_net import CorrBlock
    from src.trajectory_filler import PoseTrajectoryFiller
    from src.utils.sys_timer import timer
    from task003_observer import recorder
    from native_control.dataset import NativeViperRGB

    class ReusePriors:
        def __enter__(self):
            self.depth_factory, self.feature_factory = mf.get_metric_depth_estimator, mf.get_feature_extractor
            mf.get_metric_depth_estimator = lambda cfg: models['Metric3D']
            mf.get_feature_extractor = lambda cfg: models['FiT3D']

        def __exit__(self, *args):
            mf.get_metric_depth_estimator, mf.get_feature_extractor = self.depth_factory, self.feature_factory

    video = DepthVideo(cfg, sink)
    video.counter = counter
    slam = SimpleNamespace(cfg=cfg, device='cpu', droid_net=models['DroidNet'],
                           video=video, verbose=False, save_dir=str(OUT), printer=sink)
    with ReusePriors():
        tracker = Tracker(slam, sink, sink)
    filler = PoseTrajectoryFiller(cfg, models['DroidNet'], video, sink, device='cpu')
    stream = NativeViperRGB(cfg, INPUT, OUT)
    tracker.motion_filter.net = torch.zeros(1, 128, 45, 80)
    tracker.motion_filter.inp = tracker.motion_filter.net.clone()
    tracker.motion_filter.fmap = tracker.motion_filter.net.clone()
    tracker.frontend.last_pose = video.poses[0]
    tracker.frontend.last_disp = video.disps[0]
    tracker.frontend.last_time = video.timestamp[0]
    graph = tracker.frontend.graph
    graph.corr = CorrBlock(torch.zeros(1, 1, 128, 16, 16), torch.zeros(1, 1, 128, 16, 16))
    graph.net = torch.zeros(1, 1, 128, 45, 80)
    graph.inp = graph.net.clone()
    observer = recorder()
    observer._file = observer_file
    return {'tracker': tracker, 'stream': stream, 'filler': filler, 'observer': observer, 'timer': timer,
            'cursor': {'next_input_index': 18, 'prev_kf_idx': 11, 'curr_kf_idx': 11,
                       'prev_ba_idx': 0, 'intrinsic': stream.get_intrinsic()}}


def families_of(runtime):
    definitions = json.loads((ROOT / 'evidence/APPROVED_47_FAMILY_PROTOCOL.json').read_text())['tensors']
    tracker = runtime['tracker']
    evidence = []
    for field in definitions:
        name = field['name']
        root, *parts = name.replace('corr_pyramid[*]', 'corr_pyramid').split('.')
        value = {'video': tracker.video, 'motion_filter': tracker.motion_filter, 'frontend': tracker.frontend}[root]
        for attribute in parts:
            value = getattr(value, attribute)
        values = value if isinstance(value, list) else [value]
        assert len(values) == (4 if 'corr_pyramid' in name else 1)
        assert all(isinstance(item, torch.Tensor) for item in values)
        evidence.append({'family': name, 'views': [
            {'shape': list(item.shape), 'dtype': str(item.dtype),
             'stride': list(item.stride()), 'offset': item.storage_offset(),
             'logical_sha256': byte_sha(item.detach().contiguous().view(-1).view(torch.uint8))}
            for item in values]})
    assert len(evidence) == 47
    return evidence


def config_nodes(graph):
    rows = []
    for node_id, node in graph.nodes.items():
        if node['kind'] == TAG:
            attrs = graph.nodes[node['attrs']['$ref']]
            rows.append({'id': node_id, 'class': node['class'],
                         'items': len(node['items']),
                         'ordered_keys': [k if type(k) in (str, int, bool) else repr(k) for k, _ in node['items']],
                         'mapping_sha256': digest(node['items']), 'attributes_sha256': digest(attrs),
                         'reference_sha256': digest(node)})
    assert rows and any(row['items'] for row in rows)
    return rows


def rng_equal(left, right):
    return all(torch.equal(left[k], right[k]) if isinstance(left[k], torch.Tensor)
               else left[k] == right[k] for k in left) and left.keys() == right.keys()


def run_child(sink, counter, observer_file):
    service = {'sink': sink, 'counter': counter, 'observer_file': observer_file}
    original_rng = capture_rng_state()
    bundle, manifest = load_state(SNAPSHOT, services=service)
    state_after_load = capture_rng_state()
    graph = ObjectEncoder(services=service)
    root = graph.encode(bundle)
    if root != manifest['root'] or graph.nodes != manifest['nodes'] or graph.classes != manifest['classes']:
        diff = next((key for key in manifest['nodes'] if graph.nodes.get(key) != manifest['nodes'][key]), None)
        write_json('GRAPH_MISMATCH.json', {'node': diff, 'expected': manifest['nodes'].get(diff), 'actual': graph.nodes.get(diff)})
        raise ControlError('Restored runtime graph differs at ' + str(diff))
    target_configs = json.loads((OUT / 'CONFIGDICT_SOURCE_GRAPH.json').read_text())
    assert config_nodes(graph) == target_configs
    runtime = bundle['runtime']
    tracker = runtime['tracker']
    assert tracker.motion_filter.video is tracker.frontend.graph.video is runtime['filler'].video is tracker.video
    assert tracker.net is bundle['models']['DroidNet']
    assert tracker.motion_filter.metric_depth_estimator is bundle['models']['Metric3D']
    assert tracker.motion_filter.feat_extractor is bundle['models']['FiT3D']
    assert tracker.video.counter is counter
    assert runtime['observer']._file is observer_file
    assert families_of(runtime) == json.loads((OUT / 'SOURCE_47_FAMILIES.json').read_text())
    assert bundle['first_callable'] is bundle['same_callable'] is bundle['callable_owner'].lora_dropout
    assert bundle['view'].untyped_storage()._cdata == bundle['base'].untyped_storage()._cdata
    assert (tuple(bundle['view'].shape), bundle['view'].stride(), bundle['view'].storage_offset()) == ((3, 4), (8, 2), 1)
    for sid, storage in graph.storages.items():
        expected = manifest['storages'][sid]
        assert storage_key(expected) == storage_key({
            'byte_size': storage['raw'].numel(), 'raw_sha256': byte_sha(storage['raw']),
            'device': storage['device'], 'cpu_shared': storage['shared']})
    restore_rng_state(bundle['rng'])
    assert rng_equal(capture_rng_state(), bundle['rng'])
    result, _ = fixture.evaluate(bundle['models'])
    expect = json.loads((OUT / 'EXPECTED_FORWARD.json').read_text())
    if result != expect:
        write_json('FORWARD_MISMATCH.json', {'expected': expect, 'actual': result})
        raise ControlError('Fixed-input output SHA mismatch')
    assert result['identity_callables_tested'] == 71
    assert rng_equal(capture_rng_state(), bundle['rng'])
    assert not torch.cuda.is_initialized() and bundle['source_pid'] != os.getpid()
    write_json('FRESH_PROCESS_RECEIPT.json', {
        'status': 'PASS', 'fresh_pid': os.getpid(), 'source_pid': bundle['source_pid'],
        'graph_nodes': len(graph.nodes), 'unique_storage_files': len(graph.storages),
        'ConfigDict_nodes': len(target_configs), 'required_tracker_families': 47,
        'graph_reencode_equal': True, 'all_raw_storages_equal': True, 'alias_checks_equal': True,
        'RNG_equal': True, 'load_rng_unchanged': rng_equal(original_rng, state_after_load),
        'forward_and_gradient_all_exact_SHA_equal': True, 'CUDA_initialized': False,
        'outputs': result,
    })


def run_parent(sink, counter, observer_file):
    prior = read_manifest(OLD, ARCHIVE_SHA)
    assert len(prior['files']) == 798
    cfg = yaml.safe_load(Path(BASE_CONFIG).read_text())
    cfg['device'] = 'cpu'
    cfg['data']['output'] = str(OUT)
    random.seed(43)
    np.random.seed(43)
    torch.manual_seed(43)
    print('BUILD_REAL_WEIGHTED_MODELS', flush=True)
    models = fixture.models_build(cfg)
    print('CHECK_HISTORICAL_FORWARD_SHA', flush=True)
    expected, values = fixture.evaluate(models)
    del values
    historical = json.loads((OLD_RUN / 'EXPECTED_FORWARD.json').read_text())
    assert expected == historical, 'Fresh CPU fixture reference does not match the archived output SHA'
    write_json('EXPECTED_FORWARD.json', expected)
    rng = capture_rng_state()
    first = next(m for m in models['Metric3D'].modules() if type(m).__qualname__ == 'LoRALinear')
    base = torch.arange(24, dtype=torch.float32).reshape(3, 8)
    payload = {'first_callable': first.lora_dropout, 'models': models, 'same_callable': first.lora_dropout,
               'callable_owner': first, 'base': base, 'view': base[:, 1::2], 'source_pid': os.getpid(), 'rng': rng}
    real_configs = ObjectEncoder()
    real_configs.encode(models['Metric3D'])
    write_json('METRIC3D_CONFIGDICT_INSTANCES.json', config_nodes(real_configs))
    del real_configs
    print('BUILD_CPU_TRACKER_CLOSURE', flush=True)
    runtime = make_runtime(cfg, models, sink, counter, observer_file)
    payload['runtime'] = runtime
    write_json('SOURCE_47_FAMILIES.json', families_of(runtime))
    services = {'sink': sink, 'counter': counter, 'observer_file': observer_file}
    graph = ObjectEncoder(services=services)
    encoded = graph.encode(payload)
    write_json('CONFIGDICT_SOURCE_GRAPH.json', config_nodes(graph))
    print('SEAL_WITH_REUSED_HISTORICAL_TENSOR_FILES', flush=True)
    publish_cpu_fixture(encoded, graph, prior)
    del graph, payload, runtime, models
    print('RESTORE_IN_FRESH_PID', flush=True)
    with (OUT / 'restore_child.stdout.txt').open('xb') as stdout, (OUT / 'restore_child.stderr.txt').open('xb') as stderr:
        child = subprocess.run([sys.executable, '-B', '-u', __file__, str(OUT), '--child'],
                               stdout=stdout, stderr=stderr, timeout=1100)
    write_json('FRESH_PROCESS_EXIT.json', {'exit_code': child.returncode,
                                          'stdout_sha256': file_sha(OUT / 'restore_child.stdout.txt'),
                                          'stderr_sha256': file_sha(OUT / 'restore_child.stderr.txt')})
    assert child.returncode == 0, 'Fresh child failed; see its stderr and evidence'
    assert not torch.cuda.is_initialized()
    preserved = read_manifest(OLD, ARCHIVE_SHA)
    assert prior == preserved
    write_json('HISTORICAL_CPU_SNAPSHOT_PRESERVED.json',
               {'state_sha256': ARCHIVE_SHA, 'manifest_files': 800, 'all_file_SHA_match': True,
                'original_content_modified': False, 'hard_links_to_validated_payloads': True})
    print('WEIGHTED_CPU_ROUNDTRIP_PASS', flush=True)


if __name__ == '__main__':
    import torch.multiprocessing as mp
    is_child = '--child' in sys.argv
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == '' and not torch.cuda.is_initialized()
    os.environ['GAMECAM_TASK003_OBSERVER_JSONL'] = str(OUT / 'observer_log.jsonl')
    sink = Sink()
    counter = mp.get_context('spawn').Value('i', 0)
    path = OUT / ('fixture_restored_sink.jsonl' if is_child else 'fixture_source_sink.jsonl')
    try:
        with path.open('x', encoding='ascii') as observer_file:
            func = run_child if is_child else run_parent
            func(sink, counter, observer_file)
    except BaseException:
        write_json('CHILD_FAILURE.json' if is_child else 'PARENT_FAILURE.json',
                   {'traceback': traceback.format_exc(), 'CUDA_initialized': torch.cuda.is_initialized()})
        raise
