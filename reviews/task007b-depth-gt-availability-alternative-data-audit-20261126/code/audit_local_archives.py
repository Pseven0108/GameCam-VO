"""Inspect every discovered local ZIP central directory, regardless of filename.

No payload extraction, GPU, models, calibration or downloads. Non-ZIP containers
and unparseable archives remain explicit inventory limitations.
"""
from __future__ import annotations
import collections
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import time
import zipfile

from data_contracts import member_modality, viper_member

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]


def sha(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def dump(name, obj):
    p = ROOT / name; p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, allow_nan=False); f.write("\n")


def table(name, rows):
    p = ROOT / name; p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1"
    start = time.perf_counter()
    cmd = ["rg", "--files", "--hidden", "--no-ignore", "-g", "*.zip", "-g", "*.tar", "-g", "*.tar.gz", "-g", "*.tgz", "-g", "*.7z", "-g", "!**/.git/**"]
    scan = subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True, encoding="utf-8", check=True)
    archives = {PROJECT / p for p in scan.stdout.splitlines()}
    extra = [Path.home() / "Downloads", Path.home() / "Desktop"]
    for folder in extra:
        if folder.exists():
            archives.update(p for p in folder.iterdir() if p.is_file() and (p.suffix.lower() in {".zip", ".tar", ".tgz", ".7z"} or p.name.lower().endswith(".tar.gz")))
    all_rows = []; relevant = []; depth_candidates = []; protected = []
    for p in sorted(archives, key=lambda p: str(p).lower()):
        size = p.stat().st_size
        row = {"archive": str(p), "bytes": size, "status": None, "members": None,
               "VIPER_layout_members": 0, "VIPER_potential_depth_members": 0,
               "VIPER_modality_counts": "{}", "central_directory_identity_sha256": None,
               "payload_CRC_checked": False}
        if p.suffix.lower() != ".zip":
            row["status"] = "NON_ZIP_NOT_PARSED_NO_EXHAUSTIVENESS_CLAIM"
            all_rows.append(row); continue
        try:
            with zipfile.ZipFile(p) as z:
                infos = z.infolist()
                identity = "\n".join(f"{i.filename}\t{i.file_size}\t{i.CRC}" for i in infos).encode("utf-8")
                v = [i for i in infos if not i.is_dir() and viper_member(i.filename)]
                counts = collections.Counter(member_modality(i.filename) for i in v)
                depth = [i for i in v if member_modality(i.filename) == "POTENTIAL_DEPTH_REQUIRES_PROVENANCE"]
                row.update(status="CENTRAL_DIRECTORY_READ", members=len(infos), VIPER_layout_members=len(v),
                           VIPER_potential_depth_members=len(depth), VIPER_modality_counts=json.dumps(dict(counts), sort_keys=True),
                           central_directory_identity_sha256=hashlib.sha256(identity).hexdigest())
                if v:
                    relevant.append({**row, "VIPER_member_examples": [i.filename for i in v[:4]],
                                     "potential_depth_members": [i.filename for i in depth]})
                depth_candidates.extend({"archive": str(p), "member": i.filename, "bytes": i.file_size, "CRC32": i.CRC,
                                         "status": "CANDIDATE_NOT_ADMITTED"} for i in depth)
        except (zipfile.BadZipFile, OSError, NotImplementedError) as e:
            row["status"] = "UNPARSED_" + type(e).__name__
        all_rows.append(row)
    table("local_audit/ALL_ARCHIVE_INSPECTION.csv", all_rows)
    dump("local_audit/CONTENT_IDENTIFIED_VIPER_ARCHIVES.json", {"archives": relevant, "potential_depth_members": depth_candidates})
    # Every historical dense catalog, including aliases outside R0.1.
    paths = [PROJECT / "audits/VIPER_R0_1_TRAIN_AND_VO_PROTOCOL_AUDIT/03_analysis/train_dense_0_catalog.json",
             PROJECT / "audits/VIPER_R0_1_TRAIN_AND_VO_PROTOCOL_AUDIT/03_analysis/train_dense_1_catalog.json",
             PROJECT / "audits/VIPER_PRIMARY_ADMISSION_R0/03_analysis/val_dense2to9_catalog.json"]
    catalogs = []
    for p in paths:
        d = json.loads(p.read_text("utf-8"))
        entries = d.get("entries", d.get("members", []))
        if not isinstance(entries, list) or not entries:
            raise RuntimeError("Inspect unexpected historical catalog schema: " + str(p))
        names = [e.get("name", e.get("filename", "")) if isinstance(e, dict) else e for e in entries]
        if not all(isinstance(n, str) and n for n in names):
            raise RuntimeError("Historical catalog has unnamed entries")
        suffix = collections.Counter(PurePosixPath(n).suffix.lower() for n in names)
        matches = [r for r in relevant if any(n in r["VIPER_member_examples"] for n in names[:4])]
        catalogs.append({"path": str(p), "sha256": sha(p), "bytes": p.stat().st_size, "members": len(names),
                         "suffix_counts": dict(suffix), "depth_candidates": [n for n in names if member_modality(n) == "POTENTIAL_DEPTH_REQUIRES_PROVENANCE"],
                         "first_members": names[:4], "scope": d.get("coverage", "Historical central-directory listing only"),
                         "original_url": d.get("url"), "content_matching_current_archives": [r["archive"] for r in matches]})
        protected.append({"path": str(p), "bytes": p.stat().st_size, "sha256": sha(p)})
    dump("local_audit/HISTORICAL_DENSE_CATALOG_AUDIT.json", {"catalogs": catalogs})
    refs = [PROJECT / "reviews/task007a-mpsfm-confidence-calibration-audit-20261126/TASK007A_ADMISSION_DECISION.json",
            PROJECT / "reviews/task007a-mpsfm-confidence-calibration-audit-20261126/FILE_SHA256_MANIFEST.json",
            PROJECT / "reviews/task006a-r2-2-depth-restoration-gt-audit-20261126/03_gt_audit/GT_QUALITY_SUMMARY.json",
            PROJECT / "reviews/task006a-r2-2-depth-restoration-gt-audit-20261126/PROTOCOL.json",
            PROJECT / "audits/VIPER_R0_1_TRAIN_AND_VO_PROTOCOL_AUDIT/01_sources/download_index_current.html"]
    for p in refs: protected.append({"path": str(p), "bytes": p.stat().st_size, "sha256": sha(p)})
    for r in protected: assert sha(r["path"]) == r["sha256"]
    dump("evidence/INPUT_PRESERVATION.json", {"files": protected, "all_unchanged": True})
    summary = {"archive_paths_discovered": len(all_rows), "ZIP_central_directories_read": sum(r["status"] == "CENTRAL_DIRECTORY_READ" for r in all_rows),
               "unparsed_containers": [r for r in all_rows if r["status"] != "CENTRAL_DIRECTORY_READ"],
               "content_identified_VIPER_archives": len(relevant), "VIPER_potential_depth_members": len(depth_candidates),
               "scope": "All discoverable archives inside project, plus top-level Downloads/Desktop; no archive-name modality regex; unreadable/non-ZIP containers remain unverified",
               "historical_dense_catalogs": len(catalogs), "historical_dense_depth_candidates": sum(len(r["depth_candidates"]) for r in catalogs),
               "no_payload_extraction": True, "no_full_archive_CRC_claim": True, "no_raw_dataset_download": True,
               "CPU_only": True, "elapsed_seconds": time.perf_counter() - start}
    dump("local_audit/LOCAL_SEARCH_SUMMARY.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "unparsed_containers"}, indent=2))
    print("Unparsed containers:", len(summary["unparsed_containers"]))


if __name__ == "__main__": main()
