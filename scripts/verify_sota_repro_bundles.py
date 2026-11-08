"""Check the three local reproduction bundles against their bound READMEs."""
from __future__ import annotations

import _bootstrap
import json
from pathlib import Path
import re

from gamecam_vo.common import PROJECT, sha256, write_json


def main():
    required = ("SUMMARY.md", "COMMANDS.md", "LOG.md", "SCIENTIFIC_CHANGELOG.md", "COMPARABILITY_REPORT.md",
                "status.json", "ANNOTATED_README.md", "PATCHES.md")
    records = []
    for method in ("droid_w", "ba_track", "pi3mos"):
        folder = PROJECT / "baselines" / method / "repro_outputs"
        old = json.loads((folder / "readme_integrity.json").read_text(encoding="utf-8"))
        source = Path(old["original_source"])
        original = source.read_bytes()
        annotated = (folder / "ANNOTATED_README.md").read_bytes()
        stripped = re.sub(rb"<!-- GAMECAM_REPRO_BEGIN -->\r?\n.*?<!-- GAMECAM_REPRO_END -->\r?\n", b"", annotated, flags=re.S)
        count = annotated.count(b"<!-- GAMECAM_REPRO_BEGIN -->")
        if not count or stripped != original:
            raise ValueError(f"{method}: README does not strip back byte-for-byte to its bound original")
        state = json.loads((folder / "status.json").read_text(encoding="utf-8"))
        if state["status"] not in ("success", "partial", "blocked", "not_run"):
            raise ValueError(f"{method}: unknown evidence outcome enum")
        files = []
        for name in required:
            path = folder / name
            if not path.is_file() or not path.stat().st_size:
                raise ValueError(f"{method}: missing or empty required evidence file {name}")
            files.append({"file": name, "sha256": sha256(path), "bytes": path.stat().st_size})
        integrity = {"original_source": str(source), "original_sha256": sha256(source),
                     "annotated_sha256": sha256(folder / "ANNOTATED_README.md"),
                     "annotations": count, "strip_round_trip": "PASS"}
        write_json(folder / "readme_integrity.json", integrity)
        records.append({"method": method, "bundle_required_files": files, "readme_integrity": integrity,
                        "outcome": state["status"], "paper_result_match": state.get("result_match"),
                        "scope": "Required evidence files and README byte round trip; does not independently establish prediction accuracy, paper-score match or model numerical equivalence"})
    write_json(PROJECT / "reports/SOTA/repro_bundle_integrity.json", {"status": "ALL_THREE_BUNDLE_FILE_AND_README_CHECKS_PASSED", "methods": records})
    print(json.dumps({"status": "ALL_THREE_BUNDLE_FILE_AND_README_CHECKS_PASSED", "required_files_per_method": len(required)}))


if __name__ == "__main__":
    main()
