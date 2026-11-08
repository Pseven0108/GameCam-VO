"""Reconstruct the actual run's frozen source diff in a fresh private folder."""
from __future__ import annotations

import _bootstrap
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

from gamecam_vo.common import PROJECT, make_run_dir, sha256, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=("ba_track", "pi3mos"), default="ba_track")
    parser.add_argument("--run-directory", type=Path)
    args = parser.parse_args()
    upstream = PROJECT / "baselines" / args.method / "upstream"
    frozen = json.loads((PROJECT / "reports/SOTA" / (args.method+"_source_snapshot.json")).read_text(encoding="utf-8"))
    if sha256(Path(frozen["archive"])) != frozen["sha256"]:
        raise ValueError("The source snapshot archive changed")
    run = args.run_directory.resolve() if args.run_directory else PROJECT / "results/E9_BA_TRACK/20261031T121816Z_mvs_mvs_0000"
    if args.method == "pi3mos" and not args.run_directory:
        parser.error("Pi3MOS requires the explicit executed result directory")
    result_root = PROJECT / "results" / ("E9_BA_TRACK" if args.method == "ba_track" else "E10_PI3MOS")
    if not run.resolve().is_relative_to(result_root.resolve()):
        raise ValueError("Expected an owned result directory for the selected method")
    contract = json.loads((run / "execution_contract.json").read_text(encoding="utf-8"))
    patch = run / "source_changes_from_upstream.patch"
    expected_patch_hash = contract.get("source_changes_from_upstream_sha256", contract.get("source_patch_sha256"))
    if sha256(patch) != expected_patch_hash:
        raise ValueError("The executed source diff changed")
    for line in patch.read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ b/"):
            relative = Path(line[6:])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Unsafe source diff path")
    out = make_run_dir(PROJECT / "data/sota_workflows/source_verification", args.method+"_actual_run")
    archive = out / "upstream_base.zip"
    # Windows Git archive otherwise applies the user's core.autocrlf=true.
    # Reconstruct from original blob LF bytes so the actual Linux patch applies.
    subprocess.check_call(["git", "-C", str(upstream), "-c", "core.autocrlf=false", "archive", "--format=zip", "--output", str(archive), frozen["upstream_base_commit"]])
    reconstructed = out / "reconstructed_source"
    reconstructed.mkdir()
    with zipfile.ZipFile(archive) as source:
        for name in source.namelist():
            target = (reconstructed / name).resolve()
            if not target.is_relative_to(reconstructed.resolve()):
                raise ValueError("Unsafe archived source path")
        source.extractall(reconstructed)
    env = os.environ.copy()
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    env["GIT_CEILING_DIRECTORIES"] = str(out.resolve())
    subprocess.check_call(["git", "-c", "core.autocrlf=false", "apply", "--whitespace=nowarn", str(patch.resolve())], cwd=reconstructed, env=env)
    checks = []
    for row in frozen["files"]:
        actual = (reconstructed / row["file"]).read_bytes()
        current = (upstream / row["file"]).read_bytes()
        checks.append({"file": row["file"], "raw_bytes_match": actual == current,
                       "current_matches_frozen_member_sha256": hashlib.sha256(current).hexdigest() == row["sha256"],
                       "LF_normalized_bytes_match": actual.replace(b"\r\n", b"\n") == current.replace(b"\r\n", b"\n"),
                       "reconstructed_sha256": hashlib.sha256(actual).hexdigest(), "snapshot_sha256": row["sha256"]})
    verified = all(r["raw_bytes_match"] and r["current_matches_frozen_member_sha256"] for r in checks)
    record = {"status": "EXECUTED_SOURCE_RECONSTRUCTION_VERIFIED" if verified else "SOURCE_BYTE_DIFFERENCES_RECORDED",
              "directory": str(out), "run": str(run), "executed_patch_sha256": sha256(patch),
              "upstream_base_commit": frozen["upstream_base_commit"], "snapshot_compatibility_commit": frozen["compatibility_commit"],
              "snapshot_archive_sha256": frozen["sha256"], "files_checked": len(checks),
              "all_raw_bytes_match": all(r["raw_bytes_match"] for r in checks),
              "all_members_match_frozen_archive": all(r["current_matches_frozen_member_sha256"] for r in checks),
              "all_LF_normalized_bytes_match": all(r["LF_normalized_bytes_match"] for r in checks), "files": checks,
              "scope": "Applied the immutable actual Linux-run patch to a fresh upstream git archive; compared every source-snapshot member to the current checkout. Windows and Linux Git can report different CRLF normalization diffs; source content is checked directly, not inferred from clean Git status."}
    write_json(out / "verification.json", record)
    write_json(run / "executed_source_verification.json", record)
    write_json(PROJECT / "reports/SOTA" / (args.method+"_executed_source_verification.json"), record)
    print(json.dumps({key: record[key] for key in ("status", "files_checked", "all_raw_bytes_match", "all_LF_normalized_bytes_match")}))
    return int(not verified)


if __name__ == "__main__":
    raise SystemExit(main())
