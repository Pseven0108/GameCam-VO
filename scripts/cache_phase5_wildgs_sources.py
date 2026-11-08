"""Byte-identical source copies on WSL ext4 avoid DrvFS traceback stat overhead."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    cache = Path("/home/lsuser/.local/share/gamecam-vo/source_cache") / (stamp+"_wildgs")
    cache.mkdir(parents=True, exist_ok=False)
    records = []
    sources = {"wildgs": ROOT / "baselines/wildgs_slam/upstream", "FiT3D": ROOT / "baselines/droid_w/prior_sources/FiT3D", "Metric3D": ROOT / "baselines/droid_w/prior_sources/Metric3D"}
    for name, source in sources.items():
        selected = []
        for parent, folders, names in os.walk(source):
            folders[:] = [name for name in folders if name not in (".git", "build", "__pycache__", "eigen", "glm", "media") and not name.endswith(".egg-info")]
            selected.extend(Path(parent) / name for name in names)
        for path in sorted(selected):
            relative = path.relative_to(source)
            if any(p in (".git", "build", "__pycache__") or p.endswith(".egg-info") for p in relative.parts):
                continue
            if not path.is_file() or path.suffix.lower() not in (".py", ".yaml", ".yml", ".json", ".glsl", ".vert", ".frag", ".txt"):
                continue
            destination = cache / name / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            original, copied = path.read_bytes(), destination.read_bytes()
            if original != copied:
                raise ValueError("Source cache byte identity failed")
            records.append({"source": str(path), "cached": str(destination), "sha256": hashlib.sha256(original).hexdigest(), "bytes": len(original)})
    for name in ("run_phase5_wildgs_entrypoint.py", "run_phase5_wildgs_cached_entrypoint.py", "run_phase5_wildgs_observed_entrypoint.py", "wildgs_phase5_observer.py"):
        source, destination = ROOT / "scripts" / name, cache / name
        shutil.copy2(source, destination)
        if source.read_bytes() != destination.read_bytes():
            raise ValueError("Launcher byte identity failed")
        records.append({"source": str(source), "cached": str(destination), "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "bytes": source.stat().st_size})
    from mmengine import Config
    checked = Config.fromfile(str(cache / "Metric3D/mono/configs/HourglassDecoder/vit.raft5.large.py"))
    if not checked:
        raise ValueError("Copied Metric3D configuration failed recursive inheritance preflight")
    record = {"status": "WSL_NATIVE_SOURCE_CACHE_BYTE_IDENTICAL", "directory": str(cache), "files": records,
              "Metric3D_recursive_config_preflight": "PASS",
              "model_or_config_math_modified": False, "anomaly_and_NaN_checks_disabled": False,
              "rationale": "Read-only profiling repeatedly sampled Python linecache.checkcache during native anomaly tracing over DrvFS source paths; preserve debugging and execute identical source on ext4"}
    (cache / "source_manifest.json").write_text(json.dumps(record, indent=2))
    (ROOT / "reports/PHASE5/wildgs_native_source_cache.json").write_text(json.dumps(record, indent=2))
    print(json.dumps({"status": record["status"], "directory": str(cache), "source_files": len(records)}), flush=True)


if __name__ == "__main__":
    main()
