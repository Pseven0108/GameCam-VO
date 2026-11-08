"""Freeze checked-out DROID source, pinned dependencies and applied diffs."""
from __future__ import annotations

import _bootstrap
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

from gamecam_vo.common import PROJECT, make_run_dir, sha256, write_json


def git(repo: Path, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def main():
    root = PROJECT / "baselines/droid_w/upstream"
    components = [("DROID_W", root)]
    for line in git(root, "submodule", "status", "--recursive").decode().splitlines():
        if line and line[0] != "-":
            relative = line[1:].split()[1]
            components.append((relative.replace("/", "__"), root / relative))
    components += [("Metric3D", PROJECT / "baselines/droid_w/prior_sources/Metric3D"),
                   ("FiT3D", PROJECT / "baselines/droid_w/prior_sources/FiT3D"),
                   ("pytorch_scatter", PROJECT / "baselines/droid_w/prior_sources/pytorch_scatter")]
    bases = {
        "DROID_W": "c3414af6047d06bafc1a6645d09f23247f3b2cdc",
        "thirdparty__lietorch": "0fa9ce8ffca86d985eca9e189a99690d6f3d4df6",
        "thirdparty__lietorch__eigen": "824272cde8ca2541e8b67b0887f5ded92b128d1f",
        "thirdparty__diff-gaussian-rasterization-w-pose": "43e21bff91cd24986ee3dd52fe0bb06952e50ec7",
        "thirdparty__diff-gaussian-rasterization-w-pose__third_party__glm": "5c46b9c07008ae65cb81ab79cd677ecc1934b903",
        "thirdparty__simple-knn": "da5f991fb5b4146531b3912d8084162cf1485701",
        "Metric3D": "eb5b6fac0dc155e4e52f576e304fbf11655ff339",
        "FiT3D": "18200c21f047b5add8b7e796d6aab97fba25e790",
        "pytorch_scatter": "140d3ad677aae615767412873b90982cbf97d35d",
    }
    out = make_run_dir(PROJECT / "data/sota_assets/DROID_W/source_snapshots", "frozen_sources")
    records = []
    archive_path = out / "checked_out_sources.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for label, repo in components:
            files = []
            for raw in git(repo, "ls-files", "-z").split(b"\0"):
                if not raw:
                    continue
                name = raw.decode("utf-8")
                path = repo / name
                if not path.is_file() or path.is_symlink() or path.suffix in (".pth", ".pt", ".ckpt", ".safetensors", ".mp4", ".zip"):
                    continue
                if path.stat().st_size > 5 * 1024 * 1024:
                    continue
                data = path.read_bytes()
                archive.writestr(label + "/" + name, data)
                files.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            diff = git(repo, "diff", bases[label], "--binary", "--ignore-submodules=all")
            (out / (label + ".patch")).write_bytes(diff)
            records.append({"component": label, "local_path": str(repo), "upstream_base_commit": bases[label], "commit": git(repo, "rev-parse", "HEAD").decode().strip(),
                            "branch": git(repo, "branch", "--show-current").decode().strip(),
                            "patch_sha256": hashlib.sha256(diff).hexdigest(), "files": files})
    status = {"directory": str(out), "archive": str(archive_path), "sha256": sha256(archive_path),
              "bytes": archive_path.stat().st_size, "components": records,
              "scope": "Existing tracked source/config/header/text files <=5MiB each; excludes weights, videos, archive assets, Git metadata and generated build output. Pinned commits plus binary diffs are retained."}
    write_json(out / "manifest.json", status)
    write_json(PROJECT / "reports/SOTA/droid_source_snapshot.json", {k: status[k] for k in ("directory", "archive", "sha256", "bytes", "scope")})
    print(json.dumps({k: status[k] for k in ("directory", "sha256", "bytes")}))


if __name__ == "__main__":
    main()
