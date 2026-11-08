"""Apply the scalar-type API fix established by the failed torch2.7 build."""
from __future__ import annotations

import _bootstrap
import json
import re

from gamecam_vo.common import PROJECT, make_run_dir, write_json


def main():
    root = PROJECT / "baselines/droid_w/upstream"
    files = [root / "src/lib/altcorr_kernel.cu", root / "src/lib/correlation_kernels.cu"]
    files += list((root / "thirdparty/lietorch/lietorch").rglob("*.cu"))
    files += list((root / "thirdparty/lietorch/lietorch/src").glob("*.cpp"))
    out = make_run_dir(PROJECT / "logs/SOTA_setup", "droid_aten_compatibility_patch")
    changes = []
    for path in files:
        old = path.read_bytes()
        new_lines, count = [], 0
        for line in old.splitlines(keepends=True):
            if b"DISPATCH" in line:
                line, n = re.subn(rb"(\b[A-Za-z_]\w*)\.type\(\)", rb"\1.scalar_type()", line)
                count += n
            new_lines.append(line)
        if count:
            path.write_bytes(b"".join(new_lines))
            changes.append({"path": path.relative_to(root).as_posix(), "dispatch_argument_replacements": count})
    write_json(out / "changes.json", {"changes": changes, "rationale": "Actual compile error: DeprecatedTypeProperties cannot convert to c10::ScalarType. Replace tensor.type() only in dispatch arguments; no kernels or arithmetic changed.",
               "trigger_log": "logs/SOTA_setup/20261030T171421_420603Z_droid_extensions/lietorch.log"})
    print(json.dumps(changes))


if __name__ == "__main__":
    main()
