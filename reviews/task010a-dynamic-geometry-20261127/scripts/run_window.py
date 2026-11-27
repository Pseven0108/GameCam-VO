"""Bounded local DROID-W frontend + native final BA + native trajectory filler.

Tracking modules are imported directly to avoid loading the unused Gaussian
mapper/desktop GUI. This is an isolated local engineering protocol, not a
repeat of the sealed R2 configuration.
"""
import argparse
import hashlib
import json
import os
import random
import sys
import time
import traceback
from pathlib import Path

import cv2
import numpy as np
import torch
import yaml

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path('/mnt/d/aaa/GameCam-VO-TASK009/external/DROID-W')
ORIGINAL = Path('/mnt/d/aaa/GameCam-VO')
WEIGHT = ORIGINAL / 'experiments/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/fresh_official_downloads/droid.pth'
RGB = ORIGINAL / 'experiments/task008_pi3mos/retrieved/outputs/night007/original_rgb'
PI3 = ORIGINAL / 'experiments/task008_pi3mos/retrieved/outputs/night007/A/predictions'
sys.path[:0] = [str(ROOT), str(SOURCE), str(SOURCE / 'thirdparty/lietorch')]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


class Stream:
    def __init__(self, ids, intrinsics, hw):
        self.ids, self.intrinsics, self.hw = ids, intrinsics, hw

    def __len__(self):
        return len(self.ids)

    def __getitem__(self, i):
        if i >= len(self):
            raise IndexError(i)
        x = cv2.cvtColor(cv2.imread(str(RGB / (f'{self.ids[i]:05d}'+IMAGE_SUFFIX))), cv2.COLOR_BGR2RGB)
        x = cv2.resize(x, self.hw[::-1], interpolation=cv2.INTER_LINEAR)
        image = torch.from_numpy(x.copy()).permute(2, 0, 1)[None].float() / 255.
        return i, image, None, None

    def get_intrinsic(self):
        return torch.tensor(self.intrinsics, dtype=torch.float32, device='cuda')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dataset', required=True)
    p.add_argument('--method', default='baseline', choices=['baseline','legacy','legacy_mean','neutral','gmos','geomotion','geometry','fusion','static','fusion_static','depth','depth_static','depth_fusion'])
    p.add_argument('--seed', type=int, default=43)
    p.add_argument('--priors', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--gate', action='store_true')
    p.add_argument('--alpha', type=float, default=1.)
    p.add_argument('--beta', type=float, default=1.)
    p.add_argument('--floor', type=float, default=.1)
    p.add_argument('--static-tracks', type=Path)
    a = p.parse_args()
    datasets=json.loads((ROOT/'experiments/TASK010-A/private/DATA_MANIFEST.json').read_text())
    dataset=next(d for d in datasets if d['name']==a.dataset)
    global RGB
    RGB=Path(dataset['rgb_dir'].replace('D:', '/mnt/d').replace(chr(92), '/'))
    global IMAGE_SUFFIX
    IMAGE_SUFFIX=dataset.get('image_suffix','.jpg')
    a.output.mkdir(parents=True, exist_ok=False)
    receipt = {'status': 'STARTED', 'gate': a.gate, 'static_tracks':str(a.static_tracks) if a.static_tracks else None, 'original_droid_slam_ran': False,
               'local_exploratory_protocol': True, 'seed': a.seed, 'dataset':a.dataset,'method':a.method, 'input_frames': 32,
               'not_formal_R2_equivalence': True,
               'gate_config':{'alpha':a.alpha,'beta':a.beta,'floor':a.floor},
               'model_prior_inference_included_in_timing':False,
               'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in
                   [Path(__file__),ROOT/'gamecam/modules/dynamic_prior/droid_adapter.py',
                    ROOT/'gamecam/modules/dynamic_prior/dynamic_mask.py',
                    ROOT/'gamecam/modules/motion_decomposition/droid_adapter.py', ROOT/'experiments/TASK010-A/scripts/task010_fusion.py']}}
    try:
        torch.set_num_threads(2)
        cv2.setNumThreads(1)
        torch.manual_seed(a.seed)
        torch.cuda.manual_seed_all(a.seed)
        np.random.seed(a.seed)
        random.seed(a.seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        from gamecam.compat.torch_scatter_python import install
        receipt['scatter_compatibility']=install()
        from src.utils.Printer import TrivialPrinter
        from src.modules.droid_net import DroidNet
        from src.depth_video import DepthVideo
        from src.frontend import Frontend
        from src.backend import Backend
        from src.trajectory_filler import PoseTrajectoryFiller
        import src.motion_filter as motion_filter_module
        from torch.utils.tensorboard import SummaryWriter
        from gamecam.modules.dynamic_prior import Pi3Cache, GateConfig
        from gamecam.modules.dynamic_prior.droid_adapter import install_video_gate

        priors = json.loads((a.priors / 'receipt.json').read_text())
        if priors['status'] != 'COMPLETE':
            raise RuntimeError('Prior cache is incomplete')
        ids = priors['rgb_ids']
        hw = priors['tracker_hw']
        k_all=np.load(RGB.parent/'intrinsics.npy',allow_pickle=False)
        k=k_all[0].copy()
        if np.max(np.abs(k_all-k))>.001:raise RuntimeError('Variable K not admitted')
        cfg = yaml.safe_load((SOURCE / 'configs/droid_w.yaml').read_text())
        cfg['setup_seed']=a.seed
        cfg.update(scene=a.dataset, debug=False, verbose=False, droidvis=False)
        cfg['data']['output'] = str(a.output)
        cfg['tracking']['buffer'] = 64
        cfg['tracking']['warmup'] = 6
        cfg['tracking']['force_keyframe_every_n_frames'] = 2
        cfg['tracking']['uncertainty_params']['visualize'] = False
        cfg['tracking']['uncertainty_params']['gamma_depth'] = .01
        cfg['cam'].update(H=hw[0], W=hw[1], H_out=hw[0], W_out=hw[1],
                          H_edge=0, W_edge=0, fx=float(k[0]), fy=float(k[1]), cx=float(k[2]), cy=float(k[3]))
        cfg['mono_prior'].update(save_depth=False, save_feature=False)
        (a.output / 'native_config.yaml').write_text(yaml.safe_dump(cfg))
        receipt.update(protocol_deviations=['32-frame local exploratory dataset '+a.dataset,
            '216x384 / buffer64 / warmup6 / force-keyframe-every2',
            'cached official priors at reduced canonical resolution with BF16',
            'serial tracking process; Gaussian mapping and live visualization not launched'],
            prior_receipt_sha256=sha(a.priors / 'receipt.json'), checkpoint_sha256=sha(WEIGHT))
        stream = Stream(ids, k, hw)

        # Validate cache and identity before changing any inference provider.
        by_depth = {r['rgb_id']: r for r in priors['depth']}
        by_feature = {r['rgb_id']: r for r in priors['features']}
        for fid in ids:
            for prefix, rows in [('depth', by_depth), ('feature', by_feature)]:
                if sha(a.priors / f'{prefix}_{fid:05d}.npy') != rows[fid]['sha256']:
                    raise RuntimeError('Prior cache hash mismatch')

        def cached_depth(model, timestamp, image, cfg, device, **unused):
            return torch.from_numpy(np.load(a.priors / f'depth_{ids[int(timestamp)]:05d}.npy', allow_pickle=False)).to(device)

        def cached_features(model, timestamp, image, cfg, device, **unused):
            return torch.from_numpy(np.load(a.priors / f'feature_{ids[int(timestamp)]:05d}.npy', allow_pickle=False)).to(device)

        motion_filter_module.get_metric_depth_estimator = lambda cfg: None
        motion_filter_module.get_feature_extractor = lambda cfg: None
        motion_filter_module.predict_metric_depth = cached_depth
        motion_filter_module.predict_img_features = cached_features
        net = DroidNet()
        state = {key.replace('module.', ''): value for key, value in torch.load(WEIGHT, map_location='cpu', weights_only=True).items()}
        for key in ['update.weight.2.weight', 'update.weight.2.bias', 'update.delta.2.weight', 'update.delta.2.bias']:
            state[key] = state[key][:2]
        net.load_state_dict(state, strict=True)
        del state
        net.cuda().eval()
        printer = TrivialPrinter()
        video = DepthVideo(cfg, printer)
        from task010_fusion import install_observer, install_fusion
        ba_calls=install_observer(video,dict(enumerate(ids)),a.output/'native_ba_observations')
        gate_calls = []
        if a.gate:
            cache = Pi3Cache({fid: PI3 / f'{fid:05d}.npz' for fid in ids}, tuple(hw))
            gate_calls = install_video_gate(video, cache, dict(enumerate(ids)),
                GateConfig(alpha=a.alpha, beta=a.beta, min_gate=a.floor), a.output / 'dynamic_gate.jsonl')
        if a.method not in ('baseline','static','depth','depth_static'):
            gate_method='fusion' if a.method=='depth_fusion' else a.method
            gate_calls=install_fusion(video,dataset,gate_method,a.output/'dynamic_fusion.jsonl')
        static_calls=[]
        if a.static_tracks:
            from gamecam.modules.motion_decomposition.droid_adapter import StaticTrackCache,install_static_targets
            static_calls=install_static_targets(video,StaticTrackCache(a.static_tracks,hw),dict(enumerate(ids)),a.output/'static_targets.jsonl')
        motion = motion_filter_module.MotionFilter(net, video, cfg, thresh=cfg['tracking']['motion_filter']['thresh'])
        frontend = Frontend(net, video, cfg)
        writer = SummaryWriter(str(a.output / 'tensorboard'))
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
        start = time.perf_counter()
        timeline = []
        with torch.inference_mode():
            for timestamp, image, _, _ in stream:
                before = video.counter.value
                force = motion.track(timestamp, image, stream.get_intrinsic())
                video._task010_phase='FRONTEND_LOCAL_BA' if frontend.is_initialized else 'INITIALIZATION'
                frontend(force, writer)
                if video.counter.value == frontend.warmup and not getattr(frontend, '_task009_second_stage_done', False):
                    frontend.initialize_second_stage(writer)
                    frontend._task009_second_stage_done = True
                timeline.append({'rgb_id': ids[timestamp], 'keyframes_before': before,
                                 'keyframes_after': video.counter.value, 'initialized': frontend.is_initialized})
                print('TRACK', timeline[-1], flush=True)
                (a.output / 'timeline.json').write_text(json.dumps(timeline, indent=2))
            torch.cuda.synchronize()
            tracking_seconds = time.perf_counter() - start
            if not frontend.is_initialized:
                raise RuntimeError('Window did not initialize')
            n = video.counter.value
            np.savez_compressed(a.output / 'before_final_ba.npz', timestamps=video.timestamp[:n].cpu().numpy(),
                                 poses_w2c=video.poses[:n].cpu().numpy())
            video.metric_depth_reg = False  # native SLAM.backend() temporary final-BA behavior
            video._task010_phase='FINAL_GLOBAL_BA'
            backend = Backend(net, video, cfg)
            backend.dense_ba(7, enable_udba=cfg['tracking']['frontend']['enable_opt_dyn_mask'])
            backend.dense_ba(12, enable_udba=cfg['tracking']['frontend']['enable_opt_dyn_mask'])
            video.metric_depth_reg = True
            n = video.counter.value
            np.savez_compressed(a.output / 'keyframes.npz', rgb_ids=np.array(ids)[video.timestamp[:n].long().cpu().numpy()],
                                poses_w2c=video.poses[:n].cpu().numpy(), disps=video.disps[:n].cpu().numpy(),
                                uncertainties=video.uncertainties[:n].cpu().numpy())
            video._task010_phase='TRAJECTORY_FILLER'
            filler = PoseTrajectoryFiller(cfg, net, video, printer)
            poses, _ = filler(stream)
            c2w = poses.inv().matrix().cpu().numpy()
            if c2w.shape != (len(ids), 4, 4) or not np.isfinite(c2w).all():
                raise RuntimeError('Incomplete trajectory')
            np.savez_compressed(a.output / 'trajectory.npz', rgb_ids=ids, c2w=c2w)
        torch.cuda.synchronize()
        writer.close()
        receipt.update(status='COMPLETE', frames=len(ids), keyframes=n, native_u_enabled=True,
            native_ba_calls=len(ba_calls), gate_calls=len(gate_calls), static_calls=len(static_calls), tracking_seconds=tracking_seconds, total_seconds=time.perf_counter() - start,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(), peak_reserved_bytes=torch.cuda.max_memory_reserved(),
            gpu=torch.cuda.get_device_name(), torch=torch.__version__, native_extension_sha256=sha(__import__('droid_backends').__file__))
        (a.output / 'timeline.json').write_text(json.dumps(timeline, indent=2))
    except BaseException as error:
        receipt.update(status='FAILED', error=str(error), traceback=traceback.format_exc())
        raise
    finally:
        (a.output / 'receipt.json').write_text(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
