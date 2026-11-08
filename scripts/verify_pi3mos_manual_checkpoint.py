"""Validate the user's official checkpoint against retained trusted ranges."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]
TOTAL = 4100235800


def local(value):
    text = str(value).replace("\\", "/")
    if os.name == "nt" and text.startswith("/mnt/d/"):
        text = "D:/" + text[7:]
    if os.name != "nt" and text.startswith("D:/"):
        text = "/mnt/d/" + text[3:]
    return Path(text)


def digest_range(path, start=0, length=None):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        stream.seek(start)
        remaining = path.stat().st_size-start if length is None else length
        while remaining:
            block = stream.read(min(8*1024*1024, remaining))
            if not block:
                raise ValueError("Unexpected EOF in a verified byte range")
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--structure-only", type=Path)
    args = parser.parse_args()
    if args.structure_only:
        from safetensors import safe_open
        with safe_open(args.structure_only, framework="pt", device="cpu") as model:
            keys = list(model.keys())
            if not keys:
                raise ValueError("Empty checkpoint")
            print(json.dumps({"status": "SAFETENSORS_CPU_STRUCTURE_PASSED", "tensor_count": len(keys), "keys": keys}))
        return
    out = ROOT / "logs/SOTA_setup" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())+"_pi3mos_manual_checkpoint")
    out.mkdir(exist_ok=False)
    model = ROOT / "data/sota_assets/PI3MOS/weights/model.safetensors"
    before = model.stat()
    if before.st_size != TOTAL:
        raise ValueError(f"Incomplete/wrong checkpoint size: {before.st_size}; expected {TOTAL}")
    transport = json.loads((ROOT / "reports/SOTA/pi3mos_weight_transport.json").read_text(encoding="utf-8"))
    plan = json.loads((local(transport["directory"]) / "transport_plan.json").read_text(encoding="utf-8"))
    checks = [{"kind": "original_prefix", "start": 0, "length": plan["seed_bytes"], "expected_sha256": plan["seed_sha256"]}]
    checks += [{"kind": f"original_segment_{s['index']}", "start": s["start"], "length": s["expected_bytes"],
                "expected_sha256": s["sha256"]} for s in transport["segments"] if s["complete"]]
    full_hash = digest_range(model)
    for row in checks:
        row["actual_sha256"] = digest_range(model, row["start"], row["length"])
        row["matched"] = row["actual_sha256"] == row["expected_sha256"]
        if not row["matched"]:
            raise ValueError("Manual checkpoint differs from the previously verified official byte ranges")
    linux_model = str(model).replace("\\", "/").replace("D:/", "/mnt/d/", 1)
    structure = subprocess.check_output(["wsl.exe", "-d", "Ubuntu", "--exec", "/home/lsuser/.local/share/gamecam-vo/envs/pi3mos/bin/python",
        str(Path(__file__).resolve()).replace("\\", "/").replace("D:/", "/mnt/d/", 1), "--structure-only", linux_model],
        text=True, encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    (out / "safetensors_structure.json").write_text(structure, encoding="utf-8")
    structure = json.loads(structure)
    after = model.stat()
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise ValueError("Checkpoint changed while validation was running")
    record = {"status": "MANUAL_OFFICIAL_CORE_CHECKPOINT_VERIFIED", "path": str(model), "bytes": TOTAL, "sha256": full_hash,
              "directory": str(out), "tensor_count": structure["tensor_count"], "known_official_range_checks": checks,
              "total_known_original_bytes_compared": sum(r["length"] for r in checks), "file_unchanged_during_validation": True,
              "source": "User reports completed download after receiving the official author-linked Google Drive URL",
              "official_url": "https://drive.google.com/file/d/145bC76pMHikhdTGkqDK0t9Ta0R7tw51v/view",
              "publisher_full_file_digest": "UNKNOWN", "manual_file_modified": False,
              "verification_scope": "Exact expected size; full local SHA256; all retained1.35GB original byte ranges match; native safetensors CPU structural validation. No independent publisher full-file digest or pretrained inference claim."}
    (out / "status.json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    (ROOT / "reports/SOTA/pi3mos_manual_checkpoint.json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({key: record[key] for key in ("status", "path", "bytes", "sha256", "tensor_count", "total_known_original_bytes_compared")}))


if __name__ == "__main__":
    main()
