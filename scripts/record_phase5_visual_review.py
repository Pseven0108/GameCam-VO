"""Record an explicit, already-performed PNG inspection with paired SVG identity."""
from __future__ import annotations

import _bootstrap
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from PIL import Image
from gamecam_vo.common import PROJECT, sha256, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    kind = parser.add_mutually_exclusive_group(required=True)
    kind.add_argument("--camera", action="store_true")
    kind.add_argument("--motion", action="store_true")
    parser.add_argument("--png", nargs="+", required=True, help="Exact relative PNG names actually inspected in the image viewer")
    parser.add_argument("--scope", required=True, help="Actual observations and interpretation limits from the inspection")
    args = parser.parse_args()
    folder = args.directory.resolve()
    if not any(folder.is_relative_to(PROJECT / "results" / name) for name in ("E15_MOVIE", "E16_BONN")):
        raise ValueError("Only new E15/E16 evidence is in scope")
    ledger_file = folder / "figure_review.json"
    if ledger_file.exists():
        raise FileExistsError("Preserve the existing completed review")
    submitted = {(folder / name).resolve() for name in args.png}
    if len(submitted) != len(args.png) or any(not p.is_relative_to(folder) or p.suffix != ".png" for p in submitted):
        raise ValueError("Require unique relative owned PNGs")
    if args.camera:
        required = set((folder / "tracking_visualization").glob("*.png")) | {folder / "gpu_memory_timeline.png"}
        report_file = folder / "evaluation_summary.json"
        pointer_file = None
    else:
        required = set(folder.glob("*.png"))
        candidates = [p for name in ("M1_evaluation.json", "M2_evaluation.json") if (p := folder / name).exists()]
        if len(candidates) != 1:
            raise ValueError("Expected exactly one actual motion report")
        report_file = candidates[0]
        pointer_file = folder.parent.parent / (report_file.stem.replace("_evaluation", "_evaluation_pointer") + ".json")
    if not required or not required.issubset(submitted):
        raise ValueError("All curated PNGs must actually have been inspected")
    files = []
    for png in sorted(submitted):
        with Image.open(png) as im:
            im.verify()
        svg = png.with_suffix(".svg")
        if ET.parse(svg).getroot().tag != "{http://www.w3.org/2000/svg}svg":
            raise ValueError("Invalid paired SVG")
        files.extend({"file": p.relative_to(folder).as_posix(), "sha256": sha256(p)} for p in (png, svg))
    report = json.loads(report_file.read_text(encoding="utf-8"))
    if report["figures_visually_reviewed"]:
        raise ValueError("A previously reviewed report requires its existing ledger")
    pointer = None
    if pointer_file:
        pointer = json.loads(pointer_file.read_text(encoding="utf-8"))
        if Path(pointer["report"]).resolve() != report_file or sha256(report_file) != pointer["sha256"]:
            raise ValueError("Motion report identity mismatch before review")
    snapshot = report_file.with_name(report_file.stem + ".before_visual_review.json")
    if snapshot.exists():
        raise FileExistsError(snapshot)
    shutil.copy2(report_file, snapshot)
    write_json(ledger_file, {"status": "VISUALLY_REVIEWED_PASS", "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
        "reviewer": "Codex; actual PNG inspection in image viewer, paired SVG XML/identity checks",
        "scope": args.scope, "files": files,
        "before_review_report": str(snapshot), "before_review_report_sha256": sha256(snapshot),
        "model_rerun_or_numeric_metric_change": False})
    report["figures_visually_reviewed"] = True
    write_json(report_file, report)
    if pointer is not None:
        pointer["sha256"] = sha256(report_file)
        write_json(pointer_file, pointer)
    else:
        write_json(PROJECT / "reports/PHASE5" / (report["method"] + "_" + folder.name + "_evaluation.json"), report)
    print(json.dumps({"status": "VISUALLY_REVIEWED_PASS", "directory": str(folder), "reviewed_PNGs": len(submitted)}))


if __name__ == "__main__":
    main()
