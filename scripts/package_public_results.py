"""Create a checked local delivery bundle, excluding raw data and native dependencies."""
from __future__ import annotations
import _bootstrap
import json
import zipfile
from pathlib import Path
from gamecam_vo.common import PROJECT, make_run_dir, run_metadata, sha256, write_json


def pointer(path):
    return Path(json.loads((PROJECT / path).read_text(encoding="utf-8"))["directory"])


def main():
    output = make_run_dir(PROJECT / "deliverables", "public_game_experiments")
    selected = set()
    for pattern in ("gamecam_vo/*.py", "datasets/**/*.py", "scripts/*.py", "scripts/*.sh", "configs/**/*.yaml", "configs/*.yaml",
                    "docs/sources/**/*", "baselines/orb_slam3/*.md", "baselines/orb_slam3/*.cc", "baselines/orb_slam3/*.patch",
                    "reports/*.md", "reports/*.json", "results/comparison/**/*.csv"):
        selected.update(p for p in PROJECT.glob(pattern) if p.is_file())
    for name in ("README.md", "requirements-lock.txt", "requirements.txt", "environment.yml", "environment-win64-explicit.txt",
                 "docs/figure_contract.md", "baselines/orb_slam3/CMakeLists.txt"):
        p = PROJECT / name
        if p.is_file():
            selected.add(p)
    # Preserve actual failed runs too. Frame-level RGB dumps and feature-match pictures are not needed for this delivery.
    for experiment in ("E0_MVS", "E0_OMNI", "E1A_MVS", "E1A_OMNI", "E5_OMNI", "E1B_OMNI"):
        for p in (PROJECT / "results" / experiment).rglob("*"):
            if p.is_file() and not any(part in ("feature_matches", "frames") for part in p.parts):
                selected.add(p)
    for prefix in (pointer("reports/latest_figures.json"), pointer("reports/latest_bundle_audit.json")):
        selected.update(p for p in prefix.rglob("*") if p.is_file())
    for pattern in ("E0*", "E1*", "E5*", "ORB_SLAM3*", "Pangolin_clone.log", "MonST3R_preflight.log", "Omni_paired*", "public_results_bundle_audit.log"):
        selected.update(p for p in (PROJECT / "logs").glob(pattern) if p.is_file())
    tests = json.loads((PROJECT / "logs/latest_tests.json").read_text())
    selected.update([Path(tests["log"]), Path(tests["junit_xml"]), PROJECT / "logs/latest_tests.json"])
    selected.update(p for p in (PROJECT / "logs").glob("acquisition*/*/download_manifest.json") if p.is_file())
    selected = sorted(selected)
    manifest = {**run_metadata(), "scope": "Local research delivery: source, pinned configs, reports, real run archives, logs and reviewed figures; raw game data, model weights and compiled dependencies excluded",
                "files": [{"path": p.relative_to(PROJECT).as_posix(), "bytes": p.stat().st_size, "sha256": sha256(p)} for p in selected]}
    archive = output / "GameCam-VO_public_experiments.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in selected:
            z.write(p, p.relative_to(PROJECT).as_posix())
        z.writestr("BUNDLE_MANIFEST.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    with zipfile.ZipFile(archive) as z:
        failure = z.testzip()
        if failure:
            raise IOError(f"ZIP CRC validation failed: {failure}")
        assert len(z.namelist()) == len(selected) + 1
    result = {"archive": str(archive), "bytes": archive.stat().st_size, "sha256": sha256(archive),
              "files": len(selected), "zip_crc_validation": "PASS"}
    write_json(output / "delivery_manifest.json", result)
    write_json(PROJECT / "reports/latest_delivery.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
