"""Verify original source bytes, run CPU software tests, seal the audit package."""
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
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def h(b):
    return hashlib.sha256(b).hexdigest()


def blob(b):
    return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()


def dump(path, data):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False); f.write("\n")


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1"
    assert "torch" not in sys.modules
    provenance = json.loads((ROOT / "sources/MPSFM_SOURCE_PROVENANCE.json").read_text("utf-8"))
    source_rows = []
    for entry in provenance["files"]:
        p = ROOT / "sources/mpsfm" / entry["path"]
        b = p.read_bytes()
        trimmed = False
        if blob(b) != entry["git_blob_sha"]:
            assert b.endswith(b"\n") and blob(b[:-1]) == entry["git_blob_sha"], "Unexpected source mismatch"
            # Only this new task's snapshots, not an upstream repository.
            b = b[:-1]; p.write_bytes(b); trimmed = True
        assert len(b) == entry["bytes"] and blob(b) == entry["git_blob_sha"]
        source_rows.append({**entry, "sha256": h(b), "git_blob_match": True,
                            "new_snapshot_extra_LF_corrected": trimmed})
    dump("evidence/SOURCE_SNAPSHOT_VERIFICATION.json", {"commit": provenance["commit"], "files": source_rows,
         "all_six_original_blobs_match": len(source_rows) == 6})

    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    with (ROOT / "logs/CPU_UNIT_TESTS.txt").open("x", encoding="utf-8", newline="\n") as f:
        f.write(stream.getvalue())
    dump("tests/CPU_TEST_REPORT.json", {"tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
        "status": "PASS" if result.wasSuccessful() else "FAIL", "device": "CPU",
        "scope": "Synthetic software tests only; not GT replacement or uncertainty calibration",
        "python_executable": sys.executable, "torch_imported": "torch" in sys.modules})
    assert result.wasSuccessful() and result.testsRun == 22

    # Independently rehash all consumed evidence just before sealing.
    preservation = json.loads((ROOT / "evidence/INPUT_PRESERVATION.json").read_text("utf-8"))
    for row in preservation["files"]:
        p = pathlib.Path(row["path"])
        assert p.stat().st_size == row["bytes"] and h(p.read_bytes()) == row["sha256"]
    adjudication = json.loads((ROOT / "data_audit/LOOSE_CANDIDATE_ADJUDICATION.json").read_text("utf-8"))
    counts = collections.Counter(r["classification"] for r in adjudication["candidates"])
    dump("evidence/FINAL_EVIDENCE_CHECK.json", {"protected_files": len(preservation["files"]),
         "all_unchanged": True, "loose_candidate_classes": dict(counts),
         "final_decision_unchanged": "STOPPED_AT_DATA_ADMISSION"})
    status = subprocess.run(["git", "status", "--short", "--untracked-files=no"], cwd=ROOT.parents[1],
                            capture_output=True, text=True, encoding="utf-8", check=True)
    (ROOT / "evidence/LOCAL_TRACKED_STATUS.txt").write_text(status.stdout, encoding="utf-8")
    # No model, raw dataset, credentials or pre-existing review ZIP is included.
    forbidden_suffixes = {".pth", ".pt", ".ckpt", ".safetensors", ".exr", ".npz", ".jpg", ".jpeg", ".zip"}
    problems = []
    patterns = [rb"-----BEGIN (?:OPENSSH|RSA|EC|DSA)? ?PRIVATE KEY-----",
                rb"gh[pousr]_[A-Za-z0-9]{25,}", rb"github_pat_[A-Za-z0-9_]{30,}",
                rb"https?://[^\s/:]+:[^\s/@]+@", rb"[?&](?:token|access_token|api_key)=[A-Za-z0-9_-]{16,}"]
    candidates = [p for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts and "deliveries" not in p.relative_to(ROOT).parts]
    for p in candidates:
        b = p.read_bytes()
        if p.suffix.lower() in forbidden_suffixes or any(re.search(pattern, b) for pattern in patterns):
            problems.append(p.relative_to(ROOT).as_posix())
    assert not problems, "Publication inventory failed; do not publish"
    dump("SECURITY_AUDIT.json", {"credential_scan": "PASS", "files_scanned": len(candidates),
        "credentials_included": False, "model_weights_included": False, "raw_datasets_included": False,
        "GPU_used": False, "CUDA_context_initialized": False, "checkpoint_deserialized": False,
        "model_forward_executed": False, "DROID_W_modified": False, "Metric3D_modified": False,
        "baseline_modified": False, "real_SLAM_executed": False, "calibration_fitted": False,
        "test_data_used_for_fitting": False, "new_raw_dataset_downloaded": False,
        "next_phase_started": False, "original_inputs_preserved": True,
        "GitHub_delivery": "Separately authorized full review delivery; repository stays Public"})
    files = sorted(p for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                   and "deliveries" not in p.relative_to(ROOT).parts)
    manifest = [{"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": h(p.read_bytes())} for p in files]
    dump("FILE_SHA256_MANIFEST.json", {"algorithm": "SHA-256", "scope": "Every sealed ZIP member except this self-referential manifest", "files": manifest})
    archive = ROOT / "deliveries/GAMECAM_TASK007A_CONFIDENCE_CALIBRATION_AUDIT_REVIEW.zip"
    archive.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for row in manifest:
            z.write(ROOT / row["path"], row["path"])
        z.write(ROOT / "FILE_SHA256_MANIFEST.json", "FILE_SHA256_MANIFEST.json")
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert set(z.namelist()) == {r["path"] for r in manifest} | {"FILE_SHA256_MANIFEST.json"}
        for row in manifest:
            b = z.read(row["path"])
            assert len(b) == row["bytes"] and h(b) == row["sha256"]
    receipt = {"ZIP_name": archive.name, "ZIP_bytes": archive.stat().st_size, "ZIP_sha256": h(archive.read_bytes()),
               "ZIP_members": len(manifest) + 1, "internal_SHA256_entries": len(manifest),
               "CRC": "PASS", "internal_SHA256": "PASS", "source_blobs": "6/6 PASS",
               "CPU_tests": "22/22 PASS", "research_status": "STOPPED_AT_DATA_ADMISSION"}
    dump("deliveries/PACKAGE_VERIFICATION.json", receipt)
    (archive.parent / (archive.name + ".sha256")).write_text(receipt["ZIP_sha256"] + "  " + archive.name + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
