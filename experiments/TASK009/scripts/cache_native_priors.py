"""Sequential official Metric3D / FiT3D inference for matched local E0/E1."""
import argparse
import gc
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torchvision import transforms
import torchvision.transforms.functional as TF

ROOT = Path(__file__).resolve().parents[3]
ORIGINAL = Path(r'D:\aaa\GameCam-VO')
WEIGHTS = ORIGINAL / 'experiments/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/fresh_official_downloads'
RGB = ORIGINAL / 'experiments/task008_pi3mos/retrieved/outputs/night007/original_rgb'
GT = ORIGINAL / 'experiments/VIPER_VAL007_STAGE_OBSERVABILITY_R2/sealed_baseline/GT_val_007_OFFLINE_ONLY.npz'


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--height', type=int, default=216)
    p.add_argument('--width', type=int, default=384)
    p.add_argument('--canonical-height', type=int, default=392)
    p.add_argument('--canonical-width', type=int, default=700)
    p.add_argument('--reuse-depths', type=Path)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(2)
    cv2.setNumThreads(1)
    torch.manual_seed(43)
    np.random.seed(43)
    ids = list(range(301, 333))
    with np.load(GT, allow_pickle=False) as z:
        lookup = {int(fid): i for i, fid in enumerate(z['rgb_ids'])}
        intrinsics = np.stack([z['raw_intrinsics'][lookup[fid]] for fid in ids])
        gt_c2w = np.stack([z['gt_c2w'][lookup[fid]] for fid in ids])
    scaled_k = intrinsics * [a.width / 1920, a.height / 1080, a.width / 1920, a.height / 1080]
    # Explicit local candidate convention; identical for both experiment arms.
    scaled_k[:, 2:] += np.array([a.width / 1920, a.height / 1080]) * .5 - .5
    np.savez_compressed(a.output / 'offline_gt.npz', rgb_ids=ids, c2w=gt_c2w, intrinsics=scaled_k)
    frames = []
    for fid in ids:
        path = RGB / f'{fid:05d}.jpg'
        image = cv2.cvtColor(cv2.imread(str(path)), cv2.COLOR_BGR2RGB)
        if image.shape != (1080, 1920, 3):
            raise ValueError('RGB geometry differs')
        frames.append(torch.from_numpy(cv2.resize(image, (a.width, a.height), interpolation=cv2.INTER_LINEAR).copy()).permute(2, 0, 1)[None].float() / 255)
    receipt = {'scope': 'LOCAL_EXPLORATORY_MATCHED_PRIOR_CACHE', 'rgb_ids': ids,
               'tracker_hw': [a.height, a.width], 'canonical_hw': [a.canonical_height, a.canonical_width],
               'precision': 'BF16 autocast; output float32', 'half_pixel_intrinsics': True,
               'deviation': 'Reduced canonical Metric3D resolution and mixed precision; not formal R2 equivalence',
               'rgb_manifest': [{'rgb_id': fid, 'sha256': sha(RGB / f'{fid:05d}.jpg')} for fid in ids],
               'checkpoints': {}, 'depth': [], 'features': []}
    # Local source, official checkpoint. No hub download is permitted at runtime.
    sys.path.insert(0, str(ROOT / 'external/Metric3D'))
    from hubconf import metric3d_vit_large
    if a.reuse_depths:
        import shutil
        for fid in ids:
            old = a.reuse_depths / f'depth_{fid:05d}.npy'
            d = np.load(old, allow_pickle=False)
            if d.shape != (a.height, a.width) or not np.isfinite(d).all() or (d < 0).any():
                raise ValueError('Invalid previously generated depth cache')
            shutil.copyfile(old, a.output / old.name)
            receipt['depth'].append({'rgb_id': fid, 'sha256': sha(old), 'reused_from': str(old)})
        receipt['depth_reuse_evidence'] = 'native_priors_r2.log: all 32 Metric3D forwards complete before FiT3D API error'
        model = None
    else:
        cache_depths(a, ids, frames, scaled_k, receipt, metric3d_vit_large)
    (a.output / 'depth_receipt.json').write_text(json.dumps(receipt, indent=2))
    gc.collect()
    torch.cuda.empty_cache()
    import timm
    model = timm.create_model('vit_small_patch14_reg4_dinov2.lvd142m', pretrained=False,
                              num_classes=0, dynamic_img_size=True, dynamic_img_pad=False)
    checkpoint = WEIGHTS / 'dinov2_reg_small_finetuned.pth'
    model.load_state_dict(torch.load(checkpoint, map_location='cpu', weights_only=True), strict=True)
    model.eval().cuda()
    receipt['checkpoints']['fit3d'] = {'sha256': sha(checkpoint), 'strict': True,
                                      'timm': timm.__version__, 'initial_pretrained_download_skipped': 'all parameters strictly overwritten'}
    h, w = a.height, a.width
    norm = transforms.Normalize([.485, .456, .406], [.229, .224, .225])
    for fid, x in zip(ids, frames):
        x = F.interpolate(norm(x), ((h // 14) * 14, (w // 14) * 14), mode='bilinear', align_corners=False).cuda()
        start = time.perf_counter()
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            features = model.get_intermediate_layers(x, n=[8, 9, 10, 11], reshape=True, norm=True)[-1][0].permute(1, 2, 0).float()
        if not torch.isfinite(features).all() or features.shape[-1] != 384:
            raise RuntimeError('Invalid FiT3D features')
        path = a.output / f'feature_{fid:05d}.npy'
        np.save(path, features.cpu().numpy())
        receipt['features'].append({'rgb_id': fid, 'shape': list(features.shape), 'seconds': time.perf_counter() - start, 'sha256': sha(path)})
        print('FEATURE', fid, flush=True)
    receipt['status'] = 'COMPLETE'
    (a.output / 'receipt.json').write_text(json.dumps(receipt, indent=2))


def cache_depths(a, ids, frames, scaled_k, receipt, metric3d_vit_large):
    model = metric3d_vit_large(pretrain=False)
    checkpoint = WEIGHTS / 'metric_depth_vit_large_800k.pth'
    state = torch.load(checkpoint, map_location='cpu', weights_only=True, mmap=True)
    mismatch = model.load_state_dict(state['model_state_dict'], strict=False, assign=True)
    allowed = {'depth_model.encoder.mask_token'}
    if set(mismatch.missing_keys) - allowed or mismatch.unexpected_keys:
        raise RuntimeError(f'Unexpected checkpoint mismatch: {mismatch}')
    if mismatch.missing_keys and not torch.equal(model.depth_model.encoder.mask_token, torch.zeros_like(model.depth_model.encoder.mask_token)):
        raise RuntimeError('Unloaded mask token is not native zero')
    del state
    gc.collect()
    model.eval().cuda()
    receipt['checkpoints']['metric3d'] = {'sha256': sha(checkpoint), 'missing_keys': mismatch.missing_keys,
                                         'allowed_native_zero_mask_token': True}
    h, w = a.height, a.width
    ch, cw = a.canonical_height, a.canonical_width
    scale = min(ch / h, cw / w)
    hh, ww = int(h * scale), int(w * scale)
    dh, dw = ch - hh, cw - ww
    norm = transforms.Normalize([.485, .456, .406], [.229, .224, .225])
    for i, (fid, x) in enumerate(zip(ids, frames)):
        x = transforms.Resize((hh, ww))(x)
        x = TF.pad(norm(x), (dw // 2, dh // 2, dw - dw // 2, dh - dh // 2), fill=0.).cuda()
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
        start = time.perf_counter()
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            depth, confidence, _ = model.inference({'input': x})
        depth = depth.float()[0, 0, dh // 2:ch - (dh - dh // 2), dw // 2:cw - (dw - dw // 2)]
        depth = F.interpolate(depth[None, None], (h, w), mode='bicubic', align_corners=False)[0, 0]
        depth = (depth * float(scaled_k[i, 0]) / 1000.).clamp(0, 300)
        if not torch.isfinite(depth).all() or (depth > 0).float().mean() < .9:
            raise RuntimeError('Invalid Metric3D depth')
        path = a.output / f'depth_{fid:05d}.npy'
        np.save(path, depth.cpu().numpy())
        torch.cuda.synchronize()
        receipt['depth'].append({'rgb_id': fid, 'seconds': time.perf_counter() - start,
                                  'peak_bytes': torch.cuda.max_memory_allocated(), 'sha256': sha(path)})
        print('DEPTH', fid, receipt['depth'][-1], flush=True)
        del x, depth, confidence, _


if __name__ == '__main__':
    main()
