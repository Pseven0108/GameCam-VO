"""Verify the observable output of one process, before archive and scoring."""
from pathlib import Path

import yaml

from archive import inventory
from contracts import BITS, IDS, INPUT_SHA, R2_K, TENSOR_SHA, need, read_json
from endpoints import read_export
from trace_audit import parse


def paths(root):
    root = Path(root)
    return root/'trajectory.npz', root/'native/traj/est_poses_full.txt', root/'keyframes.json'


def validate_attempt(root, arm, policy_sha, config_path):
    root = Path(root)
    files = inventory(root)
    for path in ('LAUNCH_INTENT.json', 'LAUNCH_RECEIPT.json', 'PROCESS_RECEIPT.json', 'process.stdout.txt', 'process.stderr.txt',
                 'model_input.json', 'model_result.json', 'tracking_child_ok.json', 'task004_policy_receipt.json',
                 'progress.json', 'policy.json', 'native_config.yaml', 'native_camera_stream.json', 'observer.jsonl',
                 'trajectory.npz', 'keyframes.json', 'native/traj/est_poses_full.txt', 'native/video.npz'):
        need(path in files, f'missing required attempt artifact: {path}')
    need(files['native/video.npz']['bytes'] > 0, 'empty native video dump')
    launched = read_json(root/'LAUNCH_RECEIPT.json')
    intent = read_json(root/'LAUNCH_INTENT.json')
    process = read_json(root/'PROCESS_RECEIPT.json')
    need(all(launched.get(key) == value for key,value in intent.items())
         and files['policy.json']['sha256'] == policy_sha
         and launched['arm'] == arm and launched['policy_sha256'] == policy_sha
         and process['pid'] == launched['pid'] and process['exit_code'] == 0
         and process['mode'] == launched['mode'] and launched['attempt_id'] == root.name,
         'launch/terminal receipt mismatch')
    policy = read_json(root/'task004_policy_receipt.json')
    need(policy == dict(arm=arm, campaign='FACTORIAL', local_dwu=list(BITS[arm]), final_phases=2,
                        policy_sha256=policy_sha), 'native policy receipt mismatch')
    doc = read_json(root/'model_input.json')
    reference = dict(manifest_sha256=INPUT_SHA, actual_loader_k=R2_K, rgb_ids=list(IDS), stride=1,
                     size=[640, 360], branch='FIXED_K_NATIVE_RESIZE', pose_inputs=0, multiprocessing='spawn')
    need(doc == reference, 'native RGB/loader contract mismatch')
    effective = yaml.safe_load((root/'native_config.yaml').read_bytes())
    expected = yaml.safe_load(Path(config_path).read_bytes())
    wanted_data = expected['data'].copy()
    wanted_data.update(output=launched['output_dir'], input_folder=launched['input_dir'])
    expected['data'] = wanted_data
    seed=launched['seed']
    need(seed in (44,45),'unauthorized seed')
    expected['setup_seed']=seed
    seed_receipt=read_json(root/'seed_receipt_main.json')
    need(seed_receipt['configured_seed']==seed and seed_receipt['torch_initial_seed']==seed,'seed receipt mismatch')
    need((root/'seed_receipt_tracking_spawn_entry.json').is_file(),'missing child RNG audit')
    need(effective == expected, 'configuration drift outside the two approved paths')
    child = read_json(root/'tracking_child_ok.json')
    model = read_json(root/'model_result.json')
    need(all(model[k] == child[k] == len(IDS) for k in ('read_frames', 'filler_frames'))
         and all(model[k] == len(IDS) for k in ('input_frames', 'poses_exported', 'valid_poses'))
         and child['scaled_rgb_tensor_sha256'] == model['scaled_rgb_tensor_sha256'] == TENSOR_SHA
         and model['pid'] == child['pid'], 'incomplete tracking/Filler or different image tensor bytes')
    need(model['trajectory_sha256'] == files['trajectory.npz']['sha256']
         and model['upstream_text_sha256'] == files['native/traj/est_poses_full.txt']['sha256'], 'output SHA mismatch')
    camera = read_json(root/'native_camera_stream.json')
    need(model['native_viewer_exit'] == 0 and model['native_camera_messages'] == camera['frustum_messages']
         and model['native_camera_messages'] > 0 and camera['pid'] == model['native_viewer_pid'],
         'native Rerun stream receipt mismatch')
    progress = read_json(root/'progress.json')
    need(progress['phase'] == 'complete' and progress['done'] == progress['n'] == len(IDS), 'incomplete progress ledger')
    trace = parse(root/'observer.jsonl', arm=arm, complete=True, expected_pid=child['pid'])
    need(trace.sha256 == files['observer.jsonl']['sha256'], 'observer file changed during validation')
    estimated, keyframes = read_export(*paths(root))
    need(len(estimated) == len(IDS) and len(keyframes) == model['keyframes'] == progress['keyframes'],
         'actual export coverage or keyframe count differs from receipt')
    return trace, estimated, keyframes
