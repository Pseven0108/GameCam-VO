"""Recheck the exact reused learned-prior bytes after a terminal native case."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil

from phase5_runtime import ROOT, digest, local, write


def read(path):
    return path.read_text(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    if os.name == "nt":
        raise RuntimeError("Inspect the actual native symlink from WSL; no model or CUDA imports")
    out = args.directory.resolve()
    allowed = ROOT / "results/E14_WILD_DYNAMIC/BA_TRACK"
    if not out.is_relative_to(allowed.resolve()):
        raise ValueError("Only the owned E14 BA capacity-repair case is eligible")
    target = out / "reused_prior_integrity_after_native.json"
    if target.exists():
        raise FileExistsError("Preserve the original post-run review")
    native = json.loads(read(out / "status.json"))
    contract = json.loads(read(out / "execution_contract.json"))
    reuse = json.loads(read(out / "native_prior_reuse.json"))
    review_file = out / "reused_native_prior_review.json"
    review = json.loads(read(review_file))
    review_hash = digest(review_file)
    if (native["status"] not in ("BA_TRACK_PIPELINE_FAILED", "BA_TRACK_PIPELINE_COMPLETED")
        or native["sequence"] != "crowd" or native["expected_frames"] != 1268
        or not contract["BA_native_prior_stages_reused"]
        or review_hash != contract["BA_native_prior_reuse_review_sha256"]
        or review_hash != reuse["source_review_sha256"]
        or digest(local(reuse["source_review"])) != review_hash
        or review["status"] != "COMPLETE_NATIVE_LEARNED_PRIORS_BYTE_AND_VALUE_REVIEWED_FOR_CAPACITY_REPAIR"
        or review["sensor_depth_or_GT_used"] or review["native_prior_arrays_modified"]):
        raise ValueError("Require the exact byte-reviewed native learned-prior reuse contract and actual terminal status")
    prior_root = local(review["cached_directory"]).resolve()
    expected_root = ROOT / "results/E14_WILD_DYNAMIC/BA_TRACK/20261101T152634Z_crowd/depth_results/unidepth_dav2/crowd"
    link = local(reuse["native_read_input_symlink"])
    if (prior_root != expected_root.resolve() or not link.is_symlink()
        or not link.is_relative_to(out) or link.resolve(strict=True) != prior_root):
        raise ValueError("The actual native read symlink must still resolve to the original reviewed cache")
    rows = review["files"]
    if len(rows) != 1268 or sorted(p.name for p in prior_root.iterdir()) != sorted(r["name"] for r in rows):
        raise ValueError("The complete original learned-prior file set changed")
    checked = []
    for index, row in enumerate(rows):
        file = local(row["file"]).resolve()
        linked_file = link / row["name"]
        if (row["frame_index"] != index or file.parent != prior_root or file.name != row["name"]
            or linked_file.resolve(strict=True) != file or file.stat().st_size != row["bytes"]
            or digest(linked_file) != row["sha256"]):
            raise ValueError("A native-read prior differs from the frozen original: "+row["name"])
        checked.append({"frame_index": index, "name": row["name"], "bytes": row["bytes"], "sha256": row["sha256"]})
    if digest(out / "input_manifest.json") != review["input_manifest_sha256"]:
        raise ValueError("The frozen full RGB/K input identity changed")
    receipt = {"status": "REUSED_NATIVE_LEARNED_PRIORS_BYTE_IDENTICAL_AFTER_TERMINAL_REPAIR",
        "reviewed_at_utc": datetime.now(timezone.utc).isoformat(), "directory": str(out),
        "native_status_sha256": digest(out / "status.json"), "native_pipeline_status_preserved": native["status"],
        "execution_contract_sha256": digest(out / "execution_contract.json"), "source_review_sha256": review_hash,
        "native_symlink": str(link), "native_symlink_target": str(prior_root), "checked_files": checked,
        "files_checked": len(checked), "source_prior_values_modified": False,
        "new_model_forwards": 0, "CUDA_imports_or_queries": 0, "external_GT_or_sensor_depth_read": False,
        "scope": "Post-terminal byte identity check of every actually linked learned prior; original numeric shape/finite/positive review is bound by its SHA, not reinterpreted as sensor depth.",
        "reviewer_source_sha256": digest(Path(__file__))}
    shutil.copy2(__file__, out / (Path(__file__).name+".executed_source"))
    write(target, receipt)
    print(json.dumps({"status": receipt["status"], "files_checked": len(checked), "report": str(target)}))


if __name__ == "__main__":
    main()
