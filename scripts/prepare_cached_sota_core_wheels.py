"""Reuse complete cached wheels only when their bytes match the official index plan."""
from __future__ import annotations

import _bootstrap
from email.parser import BytesParser
import json
from pathlib import Path
import re
import shutil
import zipfile
from urllib.request import ProxyHandler, build_opener

from gamecam_vo.common import PROJECT, make_run_dir, sha256, write_json


def normalized(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def main():
    plan = PROJECT / "logs/SOTA_setup/20261030T164732_894515Z_droid_runtime_plan/torch_plan.json"
    expected = {}
    for row in json.loads(plan.read_text())["install"]:
        name, version = row["metadata"]["name"], row["metadata"]["version"]
        if normalized(name) in ("numpy", "torchaudio"):
            continue
        expected[normalized(name), version] = row["download_info"]["archive_info"].get("hashes", {}).get("sha256")
    output = PROJECT / "data/sota_toolchains/cached_torch_2_7_1_cu128_cp310"
    output.mkdir(exist_ok=True)
    records = []
    official_pypi_hashes = {}
    metadata_evidence = []
    cache = PROJECT / "data/sota_toolchains/pip_cache_linux"
    for source in cache.rglob("*.body"):
        if source.stat().st_size < 512:
            continue
        try:
            with zipfile.ZipFile(source) as archive:
                metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
                if len(metadata_names) != 1:
                    continue
                name = metadata_names[0]
                if archive.getinfo(name).file_size > 2 * 1024 * 1024:
                    continue
                metadata = BytesParser().parsebytes(archive.read(name))
                package, version = metadata["Name"], metadata["Version"]
                if (normalized(package), version) not in expected:
                    continue
                wheel = BytesParser().parsebytes(archive.read(name.rsplit("/", 1)[0] + "/WHEEL"))
                tag = wheel.get_all("Tag")[0]
        except (zipfile.BadZipFile, KeyError, IndexError):
            continue
        checksum = sha256(source)
        expected_hash = expected[normalized(package), version]
        verification = "MATCHES_SAVED_OFFICIAL_INDEX_PLAN_SHA256"
        if expected_hash is None:
            key = normalized(package), version
            if key not in official_pypi_hashes:
                url = f"https://pypi.org/pypi/{package}/{version}/json"
                with build_opener(ProxyHandler({})).open(url, timeout=20) as response:
                    body = response.read(8 * 1024 * 1024 + 1)
                if len(body) > 8 * 1024 * 1024:
                    raise ValueError("Package metadata size cap exceeded")
                official_pypi_hashes[key] = {item["digests"]["sha256"] for item in json.loads(body)["urls"]}
                metadata_evidence.append({"package": package, "version": version, "url": url, "accepted_publisher_file_sha256": sorted(official_pypi_hashes[key])})
            if checksum not in official_pypi_hashes[key]:
                raise ValueError(f"Cached {package} {version} is not in official PyPI release hashes")
            verification = "MATCHES_OFFICIAL_PYPI_RELEASE_SHA256"
        elif checksum != expected_hash:
            continue  # A different wheel variant is not the selected index artifact.
        filename = re.sub(r"[-_.]+", "_", package).lower() + "-" + version + "-" + tag + ".whl"
        destination = output / filename
        transport = "existing_verified_copy"
        if not destination.exists():
            try:
                destination.hardlink_to(source)
                transport = "same_volume_hardlink_to_verified_complete_cached_bytes"
            except OSError:
                shutil.copy2(source, destination)
                transport = "copy_of_verified_complete_cached_bytes"
        if sha256(destination) != checksum:
            raise ValueError("Wheelhouse bytes changed")
        records.append({"package": package, "version": version, "wheel": str(destination), "bytes": destination.stat().st_size,
                        "sha256": checksum, "verification": verification, "source_cache_file": str(source), "transport": transport})
    packages = {normalized(row["package"]) for row in records}
    required = {name for name, _ in expected}
    missing = sorted(required-packages)
    out = make_run_dir(PROJECT / "logs/SOTA_setup", "cached_core_wheelhouse")
    result = {"status": "VERIFIED_CORE_WHEELHOUSE_READY" if not missing else "PARTIAL_VERIFIED_CORE_WHEELHOUSE", "directory": str(output),
              "official_plan": str(plan), "official_plan_sha256": sha256(plan), "wheels": records, "missing_packages": missing,
              "official_pypi_metadata_evidence": metadata_evidence,
              "note": "NumPy is installed at BA's requested1.24.3 separately. Recovered wheel filenames use their embedded compatible WHEEL tag; archive bytes and SHA256 remain unchanged. Zero/truncated network responses cannot pass this check."}
    write_json(out / "manifest.json", result)
    write_json(PROJECT / "reports/SOTA/cached_core_wheelhouse.json", result)
    print(json.dumps({"status": result["status"], "wheel_count": len(records), "missing_packages": missing, "directory": str(output)}))
    return int(not {"torch", "torchvision"}.issubset(packages))


if __name__ == "__main__":
    raise SystemExit(main())
