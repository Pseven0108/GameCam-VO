from __future__ import annotations
import _bootstrap
import argparse
import json
from pathlib import Path

from gamecam_vo.common import fresh_directory
from gamecam_vo.evaluation import load_trajectory
from gamecam_vo.plotting import plot_trajectory


def main():
    parser = argparse.ArgumentParser(description="Plot measured trajectories; require explicit units and provenance metadata.")
    parser.add_argument("--trajectory", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    timestamps, poses = load_trajectory(args.trajectory)
    files = plot_trajectory(timestamps, poses, fresh_directory(args.out), metadata["length_unit"],
                            "VALIDATED GT" if metadata.get("e0_passed") else "CANDIDATE - E0 NOT PASSED",
                            metadata.get("time_kind", "seconds"))
    print(json.dumps({"files": files, "out": str(args.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
