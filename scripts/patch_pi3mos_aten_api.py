"""Dispatch-only compatibility fix after the recorded Pi3MOS compiler failure."""
from __future__ import annotations

import _bootstrap
import hashlib
import json
import re
import subprocess

from gamecam_vo.common import PROJECT, make_run_dir, write_json


def main():
    root = PROJECT / "baselines/pi3mos/upstream"
    trigger = PROJECT / "logs/SOTA_setup/20261031T063730_508067Z_pi3mos_native/native_build.log"
    evidence = trigger.read_text(encoding="utf-8")
    if "DeprecatedTypeProperties" not in evidence or "c10::ScalarType" not in evidence:
        raise ValueError("Actual Pi3MOS compiler evidence is required")
    branch = subprocess.check_output(["git", "-C", str(root), "branch", "--show-current"], text=True).strip()
    if branch != "repro/2026-10-31-sm120":
        raise ValueError("The explicit reproduction branch is required")
    files = [root / "dpvo/altcorr/correlation_kernel.cu"]
    files += list((root / "dpvo/lietorch/src").glob("*.cu"))
    files += list((root / "dpvo/lietorch/src").glob("*.cpp"))
    records = []
    for path in files:
        old = path.read_bytes()
        count, lines = 0, []
        for line in old.splitlines(keepends=True):
            if b"DISPATCH" in line:
                line, replacements = re.subn(rb"(\b[A-Za-z_]\w*)\.type\(\)", rb"\1.scalar_type()", line)
                count += replacements
            lines.append(line)
        if count:
            new = b"".join(lines)
            path.write_bytes(new)
            records.append({"path": path.relative_to(root).as_posix(), "dispatch_argument_replacements": count,
                            "before_sha256": hashlib.sha256(old).hexdigest(), "after_sha256": hashlib.sha256(new).hexdigest()})
    result = {"changes": records, "trigger_log": str(trigger), "branch": branch,
              "scope": "Only tensor dtype dispatch API arguments; identical legacy LieTorch dispatch sites included. No arithmetic, model hyperparameters, iteration counts or thresholds changed.",
              "verification": "Rebuild and actual numerical CUDA probes are required"}
    out = make_run_dir(PROJECT / "logs/SOTA_setup", "pi3mos_aten_api_patch")
    write_json(out / "changes.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
