"""Read-only local admission audit. No inference, calibration or GT substitution."""
from __future__ import annotations

import collections
import csv
import hashlib
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import zipfile

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
R21 = PROJECT / "reviews/task006a-r2-1-metric3d-gpu-pilot-20261126"
R22 = PROJECT / "reviews/task006a-r2-2-depth-restoration-gt-audit-20261126"


def sha(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump(relative, data):
    p = ROOT / relative
    p.parent.mkdir(parents=True, exist_ok=True)
    binary = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if p.exists():
        if p.read_bytes() != binary:
            if p.name == "LOOSE_VIPER_CANDIDATE_SEARCH.json":
                old = json.loads(p.read_text("utf-8"))
                if old["searched_roots"] == data["searched_roots"] and sorted(old["candidate_paths"], key=lambda r: r["path"]) == sorted(data["candidate_paths"], key=lambda r: r["path"]):
                    return  # Preserve the original order of an identical snapshot.
            raise RuntimeError("Refuse to replace a changed prior audit JSON")
        return
    with p.open("xb") as f:
        f.write(binary)


def table(relative, rows):
    if not rows:
        raise ValueError("Explicit nonempty status rows required")
    p = ROOT / relative
    p.parent.mkdir(parents=True, exist_ok=True)
    stream = io.StringIO(newline="")
    w = csv.DictWriter(stream, list(rows[0]))
    w.writeheader(); w.writerows(rows)
    data = stream.getvalue().encode("utf-8")
    if p.exists():
        if p.read_bytes() != data:
            old = list(csv.DictReader(io.StringIO(p.read_text("utf-8"))))
            new = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
            if sorted(json.dumps(r, sort_keys=True) for r in old) == sorted(json.dumps(r, sort_keys=True) for r in new):
                return  # rg traversal order is unspecified; no values changed.
            raise RuntimeError("Refuse to replace a changed prior audit table")
        return
    with p.open("xb") as f:
        f.write(data)


def checked(path, expected=None):
    p = pathlib.Path(path)
    h = sha(p)
    if expected is not None and h != expected:
        raise RuntimeError("Sealed input identity mismatch: " + str(p))
    return {"path": str(p), "bytes": p.stat().st_size, "sha256": h}


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1", "Use the local CPU launcher contract"
    assert "torch" not in sys.modules
    t = time.perf_counter()
    protected = []
    evidence_paths = [
        R21 / "04_evaluation/diagnostic_zero_extension_002/RAW_OUTPUT_INDEX.json",
        R21 / "03_gt_admission/GT_ADMISSION_FINAL.json",
        R21 / "05_reports/GT_ADMISSION_AND_LIMITATIONS.md",
        R22 / "03_gt_audit/GT_QUALITY_SUMMARY.json",
        R22 / "PROTOCOL.json", R22 / "R2_2_DECISION.json", R22 / "FINAL_REVIEW.md",
        R22 / "02_restoration/torch_CPU/CPU_RESTORE_RECEIPT.json",
        PROJECT / "AGENTS.md", PROJECT / "docs/LOCAL_EXPERIMENT_WORKFLOW.md",
    ]
    for p in evidence_paths:
        protected.append(checked(p))
    for name in ["task006a-r2-1-metric3d-gpu-pilot-20261126", "task006a-r2-2-depth-restoration-gt-audit-20261126"]:
        folder = PROJECT / "reviews" / name
        manifest = json.loads((folder / "FILE_SHA256_MANIFEST.json").read_text("utf-8"))
        # Verify only files actually consumed; do not reinterpret historical tests.
        by_path = {r["path"]: r for r in manifest["files"]}
        for e in list(protected):
            p = pathlib.Path(e["path"])
            if p.is_relative_to(folder):
                k = p.relative_to(folder).as_posix()
                if k in by_path and e["sha256"] != by_path[k]["sha256"]:
                    raise RuntimeError("Historical manifest mismatch: " + k)

    index = json.loads(evidence_paths[0].read_text("utf-8"))["files"]
    receipt = json.loads((R22 / "02_restoration/torch_CPU/CPU_RESTORE_RECEIPT.json").read_text("utf-8"))
    restore_by_id = {r["sample_id"]: r for r in receipt["results"]}
    rows = []
    for row in index:
        if row["dataset"] != "VIPER":
            continue  # Never silently substitute MVS-Synth for the requested dataset.
        path = pathlib.Path(row["path"])
        protected.append(checked(path, row["sha256"]))
        restored = R22 / "02_restoration/torch_CPU" / (row["sample_id"] + ".npz")
        protected.append(checked(restored, restore_by_id[row["sample_id"]]["sha256"]))
        with np.load(path, allow_pickle=False) as source, np.load(restored, allow_pickle=False) as z:
            conf = z["native_confidence_CPU"]
            depth = z["native_bilinear_same_focal"]
            raw = source["native_confidence"]
            conf_grid_equal = conf.shape == depth.shape
            finite = np.isfinite(conf)
            qs = np.percentile(conf[finite], [0, 1, 10, 50, 90, 99, 100])
            rows.append({
                "sample_id": row["sample_id"], "dataset": "VIPER", "split": "Validation",
                "sequence": row["sequence"], "RGB_ID": row["frame_id"], "environment": row["environment"],
                "width": conf.shape[1], "height": conf.shape[0], "pixels": conf.size,
                "confidence_finite": int(finite.sum()), "confidence_nan": int(np.isnan(conf).sum()),
                "confidence_negInf": int(np.isneginf(conf).sum()), "confidence_posInf": int(np.isposinf(conf).sum()),
                "confidence_min": float(qs[0]), "confidence_P01": float(qs[1]), "confidence_P10": float(qs[2]),
                "confidence_median": float(qs[3]), "confidence_P90": float(qs[4]), "confidence_P99": float(qs[5]),
                "confidence_max": float(qs[6]), "confidence_lt_0": int((conf < 0).sum()),
                "confidence_ge_1": int((conf >= 1).sum()), "confidence_gt_1": int((conf > 1).sum()),
                "restored_vs_old_confidence_max_abs": float(np.max(np.abs(conf.astype(float) - raw.astype(float)))),
                "depth_finite_positive": int((np.isfinite(depth) & (depth > 0)).sum()),
                "depth_confidence_grid_equal": conf_grid_equal,
                "cached_GT_fields": ";".join(k for k in source.files if re.search(r"(^gt_|ground.?truth|depth_gt)", k, re.I)),
                "GT_depth": "NOT_FOUND_IN_ADMITTED_INPUTS", "GT_unit": "UNVERIFIED",
                "GT_valid_mask": "UNAVAILABLE_WITHOUT_GT", "calibration_fitted": False,
            })
    assert len(rows) == 10
    assert all(r["confidence_finite"] == r["pixels"] and r["depth_confidence_grid_equal"] for r in rows)
    table("data_audit/VIPER_CONFIDENCE_CACHE_INTEGRITY.csv", rows)

    # Central-directory-only audit: no raw image decoding, extraction, full VIPER
    # experiment or payload CRC claim. Camera matrices are not pixelwise depth GT.
    proc = subprocess.run(["rg", "--files", "--hidden", "-g", "*.zip", "-g", "!**/.git/**"],
                          cwd=PROJECT, capture_output=True, text=True, encoding="utf-8", check=True)
    archives = []
    for name in proc.stdout.splitlines():
        p = PROJECT / name
        if not re.match(r"^(train|val|test)_(img|camera|depth|disparity|disp|label|flow|scene).*[.]zip$", p.name, re.I):
            continue
        with zipfile.ZipFile(p) as z:
            infos = z.infolist()
            suffix = collections.Counter(pathlib.PurePosixPath(i.filename).suffix.lower() for i in infos if not i.is_dir())
            candidates = [i.filename for i in infos if re.search(r"(^|/)(depth|depths|disparity|disp)(/|_)|[.](exr|pfm)$", i.filename, re.I)]
            directory_data = "\n".join(f"{i.filename}\t{i.file_size}\t{i.CRC}" for i in infos).encode("utf-8")
            archives.append({"archive": str(p), "bytes": p.stat().st_size,
                             "members": len(infos), "suffix_counts": json.dumps(dict(suffix), sort_keys=True),
                             "depth_candidate_count": len(candidates), "depth_candidates_first10": ";".join(candidates[:10]),
                             "central_directory_identity_sha256": hashlib.sha256(directory_data).hexdigest(),
                             "scope": "Central-directory metadata only; no payload CRC or official completeness claim"})
    table("data_audit/LOCAL_VIPER_ARCHIVE_MODALITIES.csv", archives)
    # All known raw VIPER data are ZIP-contained RGB/camera products. Check loose
    # candidate paths in dataset roots too, without traversing unrelated projects.
    loose = []
    dataset_roots = [PROJECT / s for s in ["data", "datasets", "downloads", "audits/VIPER_R0_1_TRAIN_AND_VO_PROTOCOL_AUDIT", "audits/VIPER_R1_A_15FRAME_CPU_PILOT_LOCAL_RECOVERY_V2"]]
    searched = []
    for folder in dataset_roots:
        if not folder.exists():
            continue
        scan = subprocess.run(["rg", "--files", str(folder)], capture_output=True, text=True, encoding="utf-8")
        if scan.returncode not in [0, 1]:
            raise RuntimeError("Dataset inventory failed")
        searched.append(str(folder))
        for name in scan.stdout.splitlines():
            p = pathlib.Path(name)
            if "viper" in name.lower() and (p.suffix.lower() in [".exr", ".pfm", ".npy", ".npz", ".png", ".bin"]):
                loose.append({"path": name, "bytes": p.stat().st_size})
    dump("data_audit/LOOSE_VIPER_CANDIDATE_SEARCH.json", {"searched_roots": searched, "candidate_paths": loose,
         "scope": "Project dataset roots and known VIPER audits, not every drive or another user's project"})
    mvs = json.loads((R22 / "03_gt_audit/GT_QUALITY_SUMMARY.json").read_text("utf-8"))
    assert not any(r["depth_candidate_count"] for r in archives), "Inspect new potential GT before issuing absence conclusion"
    classified = []
    for row in loose:
        p = pathlib.Path(row["path"])
        protected.append(checked(p))
        with p.open("rb") as f:
            head = f.read(64)
        if p.suffix.lower() == ".npz":
            with np.load(p, allow_pickle=False) as z:
                fields = [{"name": k, "shape": list(z[k].shape), "dtype": str(z[k].dtype)} for k in z.files]
            if {r["name"] for r in fields} != {"u", "v"} or "\\flow\\" not in str(p):
                raise RuntimeError("New unclassified NPZ candidate; inspect before continuing")
            category = "OPTICAL_FLOW_U_V_NOT_DEPTH_GT"
        elif p.suffix.lower() == ".bin":
            fields = []
            if head.startswith(b"<!DOCTYPE html>"):
                category = "HISTORICAL_HTML_DOWNLOAD_RESPONSE_NOT_DEPTH_MAP"
            elif head.startswith(b"PK\x03\x04"):
                category = "HISTORICAL_ZIP_RANGE_FRAGMENT_NOT_ADMITTED_DEPTH_GT"
            elif head.startswith(b"PK\x01\x02"):
                category = "HISTORICAL_ZIP_CENTRAL_DIRECTORY_NOT_DEPTH_MAP"
            elif p.name.endswith("_tail.bin"):
                category = "HISTORICAL_ARCHIVE_TAIL_UNVERIFIED_NOT_ADMITTED_GT"
            else:
                raise RuntimeError("Unclassified binary candidate; inspect before continuing")
        else:
            raise RuntimeError("Unclassified possible GT file; stop for inspection")
        classified.append({**row, "header_hex_first24": head[:24].hex(), "classification": category,
                           "NPZ_fields": fields, "admitted_as_GT": False})
    dump("data_audit/LOOSE_CANDIDATE_ADJUDICATION.json", {"candidates": classified,
         "no_range_fragment_decoded_or_promoted_to_GT": True,
         "no_claim_these_fragments_prove_official_archive_completeness": True})
    gate = {"task": "TASK007A", "status": "STOPPED_AT_DATA_ADMISSION", "research_decision": "NO_GO_FOR_CONFIDENCE_CALIBRATION",
            "reason": "No admitted pixelwise VIPER depth GT, confirmed GT unit or GT-valid mask; do not substitute MVS-Synth",
            "VIPER_cached_RGB": len(rows), "VIPER_environments": sorted({r["environment"] for r in rows}),
            "VIPER_cached_split": "Validation", "VIPER_confidence_finite": sum(r["confidence_finite"] for r in rows),
            "VIPER_predicted_grid_pixels": sum(r["pixels"] for r in rows),
            "VIPER_matched_admitted_depth_GT_frames": 0, "VIPER_confirmed_GT_valid_pixels": None,
            "VIPER_GT_unit": "UNVERIFIED", "VIPER_GT_valid_mask": "UNAVAILABLE",
            "MVS_is_not_VIPER": True, "MVS_existing_GT_frames": mvs["GT_frames"],
            "MVS_physical_metric_unit": mvs["physical_metric_unit"],
            "MVS_new_error_analysis_executed": False, "new_calibration_fits": 0,
            "test_data_used_for_fit": False, "new_GPU_forwards": 0, "new_data_download_bytes": 0,
            "GT_scale_fitted": False, "new_SLAM_runs": 0, "Scalix_head_need": "NOT_ESTABLISHED",
            "local_VIPER_archives_inspected": len(archives), "no_claim_official_VIPER_lacks_depth": True}
    dump("TASK007A_ADMISSION_DECISION.json", gate)
    envs = []
    for env in ["Day", "Sunset", "Rain", "Night", "Snow"]:
        sub = [r for r in rows if r["environment"] == env]
        envs.append({"environment": env, "cached_RGB": len(sub), "GT_paired_frames": 0,
                     "status": "NOT_COMPUTED_GT_ADMISSION_FAILED", "NLL": None,
                     "coverage_50pct": None, "coverage_90pct": None, "coverage_95pct": None,
                     "calibration_curve_points": None, "error_bins": None,
                     "source": "Observed cached predictions, not calibration evidence"})
    table("metrics/ENVIRONMENT_CALIBRATION_STATUS.csv", envs)
    dump("metrics/ERROR_BINS_NLL_COVERAGE.json", {"status": "NOT_COMPUTED_GT_ADMISSION_FAILED", "environments": envs,
        "depth_error_bins": None, "global_NLL": None, "global_coverage": None,
        "zero_values_are_not_missing_values": True, "any_GT_fitted_parameters": False})
    after = [checked(e["path"], e["sha256"]) for e in protected]
    dump("evidence/INPUT_PRESERVATION.json", {"files": protected, "after_files": after,
        "checked": len(protected), "all_unchanged": True})
    dump("evidence/EXECUTION_RECEIPT.json", {"device_used": "CPU", "python": sys.version, "executable": sys.executable,
        "numpy": np.__version__, "CUDA_VISIBLE_DEVICES": os.environ["CUDA_VISIBLE_DEVICES"],
        "torch_imported": "torch" in sys.modules, "GPU_used": False, "checkpoint_deserialized": False,
        "real_data_experiment": "Admission and finite/grid/Confidence integrity checks only",
        "fits": 0, "model_forwards": 0, "elapsed_seconds": time.perf_counter() - t})
    print(json.dumps(gate, indent=2))


if __name__ == "__main__":
    main()
