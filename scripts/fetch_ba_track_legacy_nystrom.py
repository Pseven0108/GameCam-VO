"""Retrieve the exact author-version Python component removed from new xFormers."""
from __future__ import annotations

import _bootstrap
import hashlib
import json
import tarfile
from urllib.request import ProxyHandler, build_opener

from gamecam_vo.common import PROJECT, make_run_dir, sha256, write_json


def main():
    folder = PROJECT / "data/sota_assets/BA_TRACK/source_archives"
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / "xformers-0.0.23.tar.gz"
    expected = "9dbc9a4a2a426e6e006417e762c54e3eb32265dde1091419d13fa683ab70559b"
    url = "https://files.pythonhosted.org/packages/66/fe/0954087306dcbc8cbffb6141748b3f1e4c6fd2203386783ee8d61cf995bb/xformers-0.0.23.tar.gz"
    if not archive.exists():
        with build_opener(ProxyHandler({})).open(url, timeout=30) as response:
            body = response.read(3847346 + 1)
        if len(body) != 3847346 or hashlib.sha256(body).hexdigest() != expected:
            raise ValueError("Official xFormers0.0.23 source archive size/hash mismatch")
        archive.write_bytes(body)
    if sha256(archive) != expected:
        raise ValueError("Stored source archive changed")
    destination = PROJECT / "baselines/ba_track/prior_sources/xformers_0_0_23"
    destination.mkdir(parents=True, exist_ok=True)
    records = []
    with tarfile.open(archive) as source:
        for member_name, filename in [("xformers-0.0.23/xformers/components/attention/nystrom.py", "nystrom.py"), ("xformers-0.0.23/LICENSE", "LICENSE")]:
            member = source.getmember(member_name)
            if not member.isfile() or member.size > 1024 * 1024:
                raise ValueError("Unexpected legacy component archive member")
            data = source.extractfile(member).read()
            (destination / filename).write_bytes(data)
            records.append({"source_archive_member": member_name, "destination": str(destination / filename), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    out = make_run_dir(PROJECT / "logs/SOTA_setup", "ba_track_legacy_nystrom_source")
    record = {"status": "OFFICIAL_LEGACY_PYTHON_COMPONENT_VERIFIED", "source_version": "xformers0.0.23", "publisher": "official PyPI release metadata",
              "source_url": url, "archive_bytes": archive.stat().st_size, "archive_sha256": expected, "files": records,
              "binary_extension_installed": False, "purpose": "Restore the same NystromAttention Python class used by the author; preserve modern sm120 CUDA kernels"}
    write_json(out / "manifest.json", record)
    write_json(PROJECT / "reports/SOTA/ba_track_legacy_nystrom.json", record)
    print(json.dumps(record))


if __name__ == "__main__":
    main()
