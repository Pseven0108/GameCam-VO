"""Freeze existing checked-out source; no clone, install or model execution."""
from __future__ import annotations

import _bootstrap
import argparse
import hashlib
import json
import subprocess
import zipfile

from gamecam_vo.common import PROJECT, make_run_dir, sha256, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("method", choices=("ba_track", "pi3mos"))
    args = parser.parse_args()
    base = {"ba_track": "456e094ee3ca7fbd9884ba18e68e7c0717d49a67", "pi3mos": "5e709d27324a935e364e01efc56f3128ac00bf24"}[args.method]
    repo = PROJECT / "baselines" / args.method / "upstream"

    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(repo), *arguments])

    out = make_run_dir(PROJECT / "data/sota_assets" / args.method.upper() / "source_snapshots", "checked_sources")
    records, excluded = [], []
    archive_path = out / "checked_out_sources.zip"
    with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for raw in git("ls-files", "-z").split(b"\0"):
            if not raw:
                continue
            name = raw.decode("utf-8")
            path = repo / name
            if not path.is_file() or path.is_symlink() or path.stat().st_size > 5*1024*1024 or path.suffix.lower() in (".pth", ".pt", ".ckpt", ".safetensors", ".mp4", ".zip"):
                excluded.append(name)
                continue
            data = path.read_bytes()
            archive.writestr(name, data)
            records.append({"file": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Source ZIP CRC failed")
        for row in records:
            if hashlib.sha256(archive.read(row["file"])).hexdigest() != row["sha256"]:
                raise ValueError("Source archive member hash failed")
    patch = git("diff", "--binary", base)
    (out / "changes_from_upstream.patch").write_bytes(patch)
    report = {"status": "CHECKED_SOURCE_ARCHIVE_VERIFIED", "directory": str(out), "archive": str(archive_path),
              "sha256": sha256(archive_path), "bytes": archive_path.stat().st_size, "upstream_base_commit": base,
              "compatibility_commit": git("rev-parse", "HEAD").decode().strip(), "branch": git("branch", "--show-current").decode().strip(),
              "tracked_source_worktree_status": git("status", "--porcelain", "--untracked-files=no").decode(),
              "patch_sha256": hashlib.sha256(patch).hexdigest(), "files": records, "excluded_tracked_paths": excluded,
              "scope": "Existing tracked source/config/header/text files up to5MiB. Excludes weights, large media, archives, Git metadata, generated build outputs and untracked files. Each archived member SHA and ZIP CRC reread verified."}
    write_json(out / "manifest.json", report)
    write_json(PROJECT / "reports/SOTA" / (args.method + "_source_snapshot.json"), report)
    print(json.dumps({k: report[k] for k in ("status", "directory", "compatibility_commit", "bytes", "sha256")}))


if __name__ == "__main__":
    main()
