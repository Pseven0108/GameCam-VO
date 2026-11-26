"""Actual scene-trained WildGS heads on cached FiT3D features; no retraining."""
import argparse
import hashlib
import importlib.util
import json
import time
from pathlib import Path

import numpy as np
import torch


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--priors', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    original = Path(r'D:\aaa\GameCam-VO')
    source = original / 'baselines/wildgs_slam/upstream/src/utils/dyn_uncertainty/uncertainty_model.py'
    spec = importlib.util.spec_from_file_location('task009_trained_wildgs', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = []
    arrays = {}
    torch.set_num_threads(2)
    for scene in ['WW_A', 'WW_B']:
        checkpoint = original / f'GAMECAM_WW_V3/03_runs/WILDGS/{scene}/disk_space_resume_20261105T062633Z/upstream_output/{scene}/uncertainty_mlp_weight.pth'
        model = module.MLPNetwork().eval()
        model.load_state_dict(torch.load(checkpoint, map_location='cpu', weights_only=True), strict=True)
        model.cuda()
        for fid in [301, 312, 325, 332]:
            features = torch.from_numpy(np.load(a.priors / f'feature_{fid:05d}.npy', allow_pickle=False)).contiguous().cuda()
            repeats = []
            torch.cuda.synchronize()
            start = time.perf_counter()
            for seed in [43, 44, 45, 46]:
                torch.manual_seed(seed)
                with torch.inference_mode():
                    uncertainty = model(features)
                if not torch.isfinite(uncertainty).all() or (uncertainty <= 0).any():
                    raise ValueError('Invalid trained-head output')
                repeats.append(uncertainty.cpu().numpy())
            stack = np.stack(repeats)
            arrays[f'{scene}_{fid}'] = stack
            rows.append({'training_scene': scene, 'rgb_id': fid, 'strict_load': True,
                'checkpoint_sha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                'shape': list(stack.shape), 'median': float(np.median(stack)),
                'p95': float(np.quantile(stack, .95)), 'mean_repeat_std': float(stack.std(0).mean()),
                'seconds': time.perf_counter() - start, 'pretrained_generic_detector': False})
    np.savez_compressed(a.output / 'predictions.npz', **arrays)
    result = {'status': 'SCENE_TRAINED_HEAD_TRANSFER_PROBE_COMPLETE', 'rows': rows,
              'feature_contract': '384-d FiT3D; dimensional compatibility is not distribution calibration',
              'native_functional_dropout_preserved': True, 'model_eval_still_stochastic': True,
              'accuracy_gt_available': False, 'DROID_U_replaced': False,
              'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    (a.output / 'results.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
