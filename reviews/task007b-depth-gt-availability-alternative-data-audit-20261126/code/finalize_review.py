"""Seal TASK007B actual audit evidence; no model or experiment execution."""
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]


def sha(b): return hashlib.sha256(b).hexdigest()
def blob(b): return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()
def dump(name, data):
    p = ROOT / name; p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False); f.write("\n")


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1" and "torch" not in sys.modules
    tests = json.loads((ROOT / "tests/CPU_TEST_REPORT.json").read_text("utf-8"))
    assert tests["status"] == "PASS" and tests["tests"] == 18
    sources = json.loads((ROOT / "sources/GITHUB_SOURCE_PROVENANCE.json").read_text("utf-8"))
    checked_sources = []
    for entry in sources["files"]:
        p = ROOT / "sources" / entry["path"]; b = p.read_bytes()
        if blob(b) != entry["git_blob_sha"]:
            assert b.endswith(b"\n") and blob(b[:-1]) == entry["git_blob_sha"]
            b = b[:-1]; p.write_bytes(b)  # New task's snapshot only, never baseline source.
        assert blob(b) == entry["git_blob_sha"]
        checked_sources.append({**entry, "bytes": len(b), "sha256": sha(b), "git_blob_match": True})
    dump("evidence/SOURCE_BLOB_VERIFICATION.json", {"files": checked_sources, "all_match": True})
    prior = PROJECT / "reviews/task007a-mpsfm-confidence-calibration-audit-20261126"
    original = json.loads((prior / "FILE_SHA256_MANIFEST.json").read_text("utf-8"))["files"]
    protected = []
    for entry in original:
        p = prior / entry["path"]; b = p.read_bytes()
        assert len(b) == entry["bytes"] and sha(b) == entry["sha256"]
        protected.append({"path": str(p), "bytes": len(b), "sha256": sha(b)})
    current = json.loads((ROOT / "evidence/INPUT_PRESERVATION.json").read_text("utf-8"))["files"]
    for row in current:
        b = Path(row["path"]).read_bytes(); assert len(b) == row["bytes"] and sha(b) == row["sha256"]
    dump("evidence/FINAL_PRESERVATION.json", {"TASK007A_sealed_files_checked": len(protected),
         "TASK007B_consumed_historical_files_checked": len(current), "all_unchanged": True, "TASK007A_files": protected})
    split = json.loads((ROOT / "CALIBRATION_EVALUATION_SPLIT.json").read_text("utf-8"))
    assert len({r["scene"] for r in split["groups"]}) == 5
    assert not split["adoption_approved"] and split["actual_samples_acquired"] == 0
    entry_rows = []
    for name in ["README.md", "PROJECT_STATUS.md", "REVIEW_INDEX.md", "REVIEWING.md"]:
        b = (ROOT / "project_entries" / name).read_bytes()
        assert "TASK007B" in b.decode("utf-8").splitlines()[0]
        assert "TASK007A" in b.decode("utf-8") and "VIPER" in b.decode("utf-8")
        entry_rows.append({"root_path": name, "sha256": sha(b), "bytes": len(b), "latest_heading": "TASK007B"})
    dump("evidence/STATE_ENTRY_VERIFICATION.json", {"four_entries_prepared_consistently": True,
         "published_readback_required_separately": True, "entries": entry_rows})

    candidates = [
      ["VIPER", "NO_GO", "Online submission confirmed; no admitted paired GT download", "Unverified", "Unverified", "VO mainline preserved", "Official tools + RVC depth devkit"],
      ["MVS-Synth", "EXPLORATORY_SHAPE_ONLY_CANDIDATE", "Existing EXR; observed0000/0001", "Physical unit not established", "Finite positive existing GT only; provenance limits remain", "No absolute-scale uncertainty certificate", "Sealed R2.2"],
      ["Virtual KITTI 2.0.3", "PREFERRED_METADATA_CANDIDATE", "Synthetic uint16 PNG Z-depth", "1 unit=0.01m documented", "Need verified zero/saturation/Sky/Undefined policy", "No Night/Snow; 5 correlated base scenes", "Official NAVER docs + HEAD + MD5 text"],
      ["TartanAir v1", "SECONDARY_METADATA_CANDIDATE", "Synthetic NPY depth", "Meters documented; actual dtype/definition check pending", "Finite distant sky; version-specific mask required", "Keep related maps/day/night in same group", "Official fixed tools docs"],
      ["NYUv2", "REAL_SENSOR_AUXILIARY_CANDIDATE", "Kinect aligned rawDepths + separate inpainting", "Meters documented", "Raw sensor holes; do not treat all inpainted pixels as measurements", "Indoor; scene split; pretraining overlap unverified", "Official NYU dataset page"]
    ]
    with (ROOT / "DATASET_CANDIDATE_MATRIX.csv").open("x", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["dataset", "decision", "GT", "unit", "validity_limit", "research_limit", "primary_evidence"]); w.writerows(candidates)
    status = subprocess.run(["git", "status", "--short", "--untracked-files=no"], cwd=PROJECT,
                            capture_output=True, text=True, encoding="utf-8", check=True)
    (ROOT / "evidence/LOCAL_TRACKED_STATUS.txt").write_text(status.stdout, encoding="utf-8")
    files = [p for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts and "deliveries" not in p.relative_to(ROOT).parts]
    patterns = [rb"-----BEGIN (?:OPENSSH|RSA|EC|DSA)? ?PRIVATE KEY-----", rb"gh[pousr]_[A-Za-z0-9]{25,}",
                rb"github_pat_[A-Za-z0-9_]{30,}", rb"[?&](?:token|access_token|api_key)=[A-Za-z0-9_-]{16,}"]
    assert not any(re.search(pattern, p.read_bytes()) for p in files for pattern in patterns), "Credential scan must pass"
    assert not any(p.suffix.lower() in {".pth", ".pt", ".ckpt", ".safetensors", ".exr", ".npz", ".jpg", ".png"} for p in files)
    dump("SECURITY_AUDIT.json", {"CPU_only": True, "torch_imported": False, "GPU_used": False, "CUDA_initialized": False,
         "model_loaded": False, "checkpoint_deserialized": False, "model_forwards": 0, "raw_dataset_payload_downloaded": False,
         "full_dataset_downloaded": False, "calibration_fitted": False, "test_used_for_fit": False,
         "training_executed": False, "SLAM_executed": False, "baseline_modified": False, "historical_results_modified": False,
         "credential_scan": "PASS", "credentials_or_models_or_raw_dataset_included": False,
         "contacts_or_submissions_sent": False, "next_phase_started": False})
    files = sorted(p for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts and "deliveries" not in p.relative_to(ROOT).parts)
    rows = [{"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p.read_bytes())} for p in files]
    dump("FILE_SHA256_MANIFEST.json", {"algorithm": "SHA-256", "scope": "Every sealed ZIP member except this manifest itself", "files": rows})
    archive = ROOT / "deliveries/GAMECAM_TASK007B_DEPTH_GT_AVAILABILITY_REVIEW.zip"; archive.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for row in rows: z.write(ROOT / row["path"], row["path"])
        z.write(ROOT / "FILE_SHA256_MANIFEST.json", "FILE_SHA256_MANIFEST.json")
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and set(z.namelist()) == {r["path"] for r in rows} | {"FILE_SHA256_MANIFEST.json"}
        for r in rows:
            b = z.read(r["path"]); assert len(b) == r["bytes"] and sha(b) == r["sha256"]
    receipt = {"ZIP_name": archive.name, "ZIP_bytes": archive.stat().st_size, "ZIP_sha256": sha(archive.read_bytes()),
               "ZIP_members": len(rows) + 1, "internal_SHA256_entries": len(rows), "CRC": "PASS", "internal_SHA256": "PASS",
               "CPU_tests": "18/18 PASS", "research_status": "DATA_SOURCE_REVIEW_COMPLETE_CALIBRATION_BLOCKED"}
    dump("deliveries/PACKAGE_VERIFICATION.json", receipt)
    (archive.parent / (archive.name + ".sha256")).write_text(receipt["ZIP_sha256"] + "  " + archive.name + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__": main()
