"""Review complete unchanged learned priors for one failed capacity repair."""
from __future__ import annotations

import _bootstrap
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

import numpy as np

from gamecam_vo.common import PROJECT, sha256, write_json
from phase5_motion_support import read, local


def main():
    old = PROJECT / "results/E14_WILD_DYNAMIC/BA_TRACK/20261101T152634Z_crowd"
    pointer_file = PROJECT / "reports/PHASE5/wild_crowd_input.json"
    pointer = read(pointer_file)
    native, contract = read(old / "status.json"), read(old / "execution_contract.json")
    if (native["status"] != "BA_TRACK_PIPELINE_FAILED" or native["stages"][-1]["stage"] != "sparse_tracker_and_BA"
        or native["stages"][-1]["exit_code"] != 1
        or read(old / "failure_review.json")["classification"] != "NATIVE_FRAME_BUFFER_CAPACITY_1024_INSUFFICIENT_FOR_FULL_1268_INPUT"):
        raise ValueError("Only the exact observed incomplete capacity failure is eligible")
    expected_stages = ["depth_anything_v2_first", "depth_anything_v2_second", "unidepth_v2", "align_predicted_depths"]
    if [r["stage"] for r in native["stages"][:4]] != expected_stages or any(r["exit_code"] or r["reason"] for r in native["stages"][:4]):
        raise ValueError("All four native learned-prior stages must have actually completed")
    manifest_file = local(pointer["directory"]) / "input_manifest.json"
    manifest = read(manifest_file)
    if sha256(manifest_file) != sha256(old / "input_manifest.json") or len(manifest["frames"]) != 1268:
        raise ValueError("Old and repair full RGB/K inputs must be identical")
    for row in manifest["frames"]:
        if sha256(local(row["path"])) != row["sha256"]:
            raise ValueError("A common RGB image changed")
    folder = old / "prior_reuse_review"
    folder.mkdir(exist_ok=False)
    cached = old / "depth_results/unidepth_dav2/crowd"
    names = sorted(p.name for p in cached.iterdir())
    expected_names = [local(r["path"]).stem+".npy" for r in manifest["frames"]]
    if names != sorted(expected_names):
        raise ValueError("Require exactly one complete final learned-prior file for every original input")
    rows = []
    for i, name in enumerate(expected_names):
        file = cached / name
        array = np.load(file, allow_pickle=False)
        if array.squeeze().shape != (240, 400) or not np.isfinite(array).all() or not (array > 0).all():
            raise ValueError("Actual learned prior shape/positivity/finite check failed: "+name)
        rows.append({"frame_index": i, "name": name, "file": str(file), "bytes": file.stat().st_size,
            "sha256": sha256(file), "shape": list(array.shape), "dtype": str(array.dtype), "minimum": float(array.min()), "maximum": float(array.max())})
    asset_file = PROJECT / "reports/SOTA/ba_track_assets.json"
    assets = read(asset_file)
    for asset in assets["assets"]:
        if Path(asset["path"]).suffix in (".pth", ".safetensors") and sha256(local(asset["path"])) != asset["sha256"]:
            raise ValueError("A selected native checkpoint changed")
    report = {"status": "COMPLETE_NATIVE_LEARNED_PRIORS_BYTE_AND_VALUE_REVIEWED_FOR_CAPACITY_REPAIR",
        "reviewed_at_utc": datetime.now(timezone.utc).isoformat(), "original_directory": str(old),
        "input_manifest_sha256": sha256(manifest_file), "input_pointer": str(pointer_file), "input_pointer_sha256": sha256(pointer_file),
        "expected_frames": 1268, "sequence": "crowd", "cached_directory": str(cached), "files": rows,
        "completed_native_prior_stages": native["stages"][:4], "original_contract_sha256": sha256(old / "execution_contract.json"),
        "original_native_status_sha256": sha256(old / "status.json"), "assets_manifest_sha256": sha256(asset_file),
        "author_prior_commands": contract["commands"][:4], "native_prior_arrays_modified": False,
        "sensor_depth_or_GT_used": False, "GT_score_used_to_select_cache": False, "new_network_forward": False,
        "timing_scope": "Prior GPU stages are reused, not executed again; new repair wall time covers only its actually executed sparse/dense stages. Original measured prior-stage times remain separate, not a new cold end-to-end FPS.",
        "reviewer_source_sha256": sha256(Path(__file__))}
    shutil.copy2(__file__, folder / "review_phase5_ba_prior_cache.py.executed_source")
    target = folder / "review.json"
    write_json(target, report)
    write_json(PROJECT / "reports/PHASE5/BA_crowd_prior_reuse_review.json", {"status": report["status"], "review": str(target), "sha256": sha256(target)})
    print(json.dumps({"status": report["status"], "files": len(rows), "report": str(target)}))


if __name__ == "__main__":
    main()
