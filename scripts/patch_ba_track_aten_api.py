"""Apply the dispatch-only API correction justified by the actual BA-Track build."""
from __future__ import annotations

import _bootstrap
import hashlib
import json
import re
import subprocess

from gamecam_vo.common import PROJECT, make_run_dir, write_json


def main():
    root = PROJECT / "baselines/ba_track/upstream"
    trigger = PROJECT / "logs/SOTA_setup/20261031T052228_389122Z_ba_track_native/native_build.log"
    text = trigger.read_text()
    if "DeprecatedTypeProperties" not in text or "c10::ScalarType" not in text:
        raise ValueError("Expected actual compiler evidence is absent")
    branch = subprocess.check_output(["git", "-C", str(root), "branch", "--show-current"], text=True).strip()
    if branch != "repro/2026-10-31-sm120":
        raise ValueError("Use the explicit reproduction branch before modifying upstream sources")
    files = [root / "main/backend/altcorr/correlation_kernel.cu"]
    files += list((root / "main/backend/lietorch/src").glob("*.cu"))
    files += list((root / "main/backend/lietorch/src").glob("*.cpp"))
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
    out = make_run_dir(PROJECT / "logs/SOTA_setup", "ba_track_aten_api_patch")
    result = {"changes": records, "trigger_log": str(trigger), "branch": branch,
              "scope": "tensor.type() to tensor.scalar_type() only on dispatch macro argument lines. Same error applies to identical legacy dispatches in bundled LieTorch. Device tests, kernels, arithmetic and model parameters are unchanged.",
              "verification": "Actual rebuild and CUDA numerical probes remain required"}
    write_json(out / "changes.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
