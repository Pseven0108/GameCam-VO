from __future__ import annotations
import _bootstrap
import argparse
from pathlib import Path
import cv2

from gamecam_vo.common import PROJECT, fingerprint, fresh_directory, read_yaml, write_csv, write_json
from gamecam_vo.video import iter_frames


def main():
    parser = argparse.ArgumentParser(description="Extract only the bounded shared clip, preserving actual video PTS and indices.")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--dataset-config", type=Path, default=PROJECT / "configs/dataset.yaml")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    config = read_yaml(args.dataset_config)
    out = fresh_directory(args.out)
    rows = []
    for frame in iter_frames(args.video, config["clip"]):
        filename = f"{frame['frame_index']:08d}.png"
        if not cv2.imwrite(str(out / filename), frame["image"]):
            raise OSError("Could not save decoded frame")
        rows.append({key: frame[key] for key in ("frame_index", "video_pts_seconds", "video_relative_seconds")} |
                    {"filename": filename})
    write_csv(out / "timestamps.csv", rows, ["frame_index", "video_pts_seconds", "video_relative_seconds", "filename"])
    write_json(out / "source.json", {"source": fingerprint(args.video), "clip": config["clip"], "extracted_frames": len(rows)})
    print(f"Extracted {len(rows)} frames to {out}")


if __name__ == "__main__":
    main()
