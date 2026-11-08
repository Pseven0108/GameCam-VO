"""Check allocator-cache equivalence on actual frozen priors and one RGB frame."""
from __future__ import annotations
import argparse
from collections import OrderedDict
import json
import os
from pathlib import Path
import sys
import time

import cv2
import numpy as np
import torch

ROOT = Path("/mnt/d/aaa/GameCam-VO")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-directory", required=True, type=Path)
    args = parser.parse_args()
    os.environ.update(GAMECAM_FIT3D_REPO=str(ROOT / "baselines/droid_w/prior_sources/FiT3D"),
                      GAMECAM_METRIC3D_REPO=str(ROOT / "baselines/droid_w/prior_sources/Metric3D"),
                      GAMECAM_XFORMERS_DISABLE_FA3="1", TORCH_HOME=str(ROOT / "data/sota_assets/DROID_W/torch_home"),
                      HF_HOME=str(ROOT / "data/sota_assets/DROID_W/huggingface"))
    upstream = ROOT / "baselines/droid_w/upstream"
    os.chdir(upstream)
    sys.path.insert(0, str(upstream))
    from src import config
    from src.modules.droid_net import DroidNet
    from src.utils.mono_priors.metric_depth_estimators import get_metric_depth_estimator, predict_metric_depth
    from src.utils.mono_priors.img_feature_extractors import get_feature_extractor, predict_img_features
    cfg = config.load_config("configs/droid_w.yaml")
    manifest = json.loads((args.input_directory / "input_manifest.json").read_text())
    k = np.array(manifest["fixed_K"])
    cfg["cam"].update(H=360, W=640, H_out=360, W_out=640, fx=float(k[0,0]), fy=float(k[1,1]), cx=float(k[0,2]), cy=float(k[1,2]))
    image = cv2.cvtColor(cv2.imread(manifest["frames"][0]["wsl_path"]), cv2.COLOR_BGR2RGB)
    image = torch.from_numpy(image.copy()).permute(2,0,1).float().unsqueeze(0)/255.
    torch.manual_seed(43)
    torch.cuda.manual_seed_all(43)
    torch.backends.cudnn.deterministic = True
    depth_model, feature_model = get_metric_depth_estimator(cfg), get_feature_extractor(cfg)
    net = DroidNet()
    weights = torch.load(ROOT / "data/sota_assets/DROID_W/weights/droid.pth", weights_only=True)
    weights = OrderedDict((key.replace("module.", ""), value) for key, value in weights.items())
    for key in ("update.weight.2.weight", "update.weight.2.bias", "update.delta.2.weight", "update.delta.2.bias"):
        weights[key] = weights[key][:2]
    net.load_state_dict(weights)
    net = net.cuda().eval()
    outputs, runs = [], []
    for enabled in (True, False):
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        start = time.monotonic()
        with torch.no_grad(), torch.autocast("cuda", enabled=True, cache_enabled=enabled):
            result = {"depth": predict_metric_depth(depth_model, 0, image, cfg, "cuda", save_depth=False).float().cpu(),
                      "features": predict_img_features(feature_model, 0, image, cfg, "cuda", save_feat=False).float().cpu()}
            mean = torch.tensor([.485,.456,.406], device="cuda")[:,None,None]
            std = torch.tensor([.229,.224,.225], device="cuda")[:,None,None]
            normalized = image[None].cuda().sub_(mean).div_(std)
            result["fnet"] = net.fnet(normalized).float().cpu()
            result["cnet"] = net.cnet(normalized).float().cpu()
        torch.cuda.synchronize()
        runs.append({"amp_weight_cache_enabled": enabled, "wall_seconds": time.monotonic()-start,
                     "peak_allocated_bytes": torch.cuda.max_memory_allocated()})
        outputs.append(result)
    checks = {}
    for key in outputs[0]:
        a, b = outputs[0][key], outputs[1][key]
        torch.testing.assert_close(a, b, rtol=1e-5, atol=1e-5)
        checks[key] = {"shape": list(a.shape), "max_absolute_difference": float((a-b).abs().max()), "bitwise_equal": bool(torch.equal(a,b)), "finite": bool(torch.isfinite(a).all() and torch.isfinite(b).all())}
        if not checks[key]["finite"]:
            raise ValueError("Nonfinite learned-prior output")
    status = {"status": "AMP_WEIGHT_CACHE_EQUIVALENCE_PASSED", "runs": runs, "checks": checks,
              "precision": "Autocast FP16 enabled in both runs; original FP32 weights unchanged", "RGB_frame": manifest["frames"][0],
              "engine_depth_or_pose_used": False, "scope": "Actual default Metric3D, FiT3D, DROID fnet/cnet; no SLAM/GT score computed"}
    out = ROOT / "logs/SOTA_setup" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "_amp_cache_equivalence")
    out.mkdir(exist_ok=False)
    (out / "result.json").write_text(json.dumps(status, indent=2))
    status["directory"] = str(out)
    (ROOT / "reports/SOTA/droid_amp_cache_equivalence.json").write_text(json.dumps(status, indent=2))
    print(json.dumps(status), flush=True)


if __name__ == "__main__":
    main()
