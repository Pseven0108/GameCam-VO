"""Decode fixed first/middle/last author-video frames without inference or GT."""
from __future__ import annotations

import _bootstrap
import argparse
from pathlib import Path
import shutil

import cv2
import numpy as np

from gamecam_vo.common import PROJECT, sha256, write_json
from phase5_motion_support import read


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    out = args.directory.resolve()
    if not any(out.is_relative_to(PROJECT / "results" / name / "BA_TRACK") for name in ("E14_WILD_DYNAMIC", "E15_MOVIE", "E16_BONN")):
        raise ValueError("Only owned new Phase5 BA cases are accepted")
    status, contract = read(out / "status.json"), read(out / "execution_contract.json")
    sparse = next(r for r in status["stages"] if r["stage"] == "sparse_tracker_and_BA")
    if sparse["exit_code"] != 0:
        raise ValueError("This video inspection requires the native sparse child to have returned successfully")
    video = out / "upstream_output" / contract["scene"] / "grid_grad_20_pred_track.mp4"
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise ValueError("Native video cannot be opened")
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    # Preserve MoviePy's actual floating-point duration and sampling semantics.
    # A short 21-image clip at 10 FPS schedules 22 encoded frames, with its
    # final source image repeated. This is display support, not another pose.
    package = Path("//wsl.localhost/Ubuntu/home/lsuser/.local/share/gamecam-vo/envs/ba-track/lib/python3.10/site-packages/moviepy")
    sequence_source, clip_source = package / "video/io/ImageSequenceClip.py", package / "Clip.py"
    sequence_text, clip_text = sequence_source.read_text(), clip_source.read_text()
    if ("self.duration = sum(durations)" not in sequence_text or
        "1.0*i/fps-np.finfo(np.float32).eps" not in sequence_text or
        "np.arange(0, self.duration, 1.0/fps)" not in clip_text):
        raise ValueError("Review actual installed MoviePy timing semantics before mapping display frames")
    selected_input_keys = np.arange(contract["expected_frames"])[2:-1]
    if not len(selected_input_keys) or not np.isfinite(fps) or fps <= 0:
        raise ValueError("Invalid native display support or encoded FPS")
    times = np.arange(0, sum([1.0 / fps] * len(selected_input_keys)), 1.0 / fps)
    starts = np.arange(len(selected_input_keys), dtype=float) / fps - np.finfo(np.float32).eps
    image_indices = np.searchsorted(starts, times, side="right") - 1
    if count != len(times) or (image_indices < 0).any() or (image_indices >= len(selected_input_keys)).any():
        raise ValueError("Encoded display count differs from the actual native MoviePy schedule")
    input_keys = selected_input_keys[image_indices]
    folder = out / "native_qualitative_examples"
    folder.mkdir(exist_ok=False)
    examples = []
    for index in sorted({0, (count - 1) // 2, count - 1}):
        if not capture.set(cv2.CAP_PROP_POS_FRAMES, index):
            raise ValueError("Native video seek failed")
        ok, image = capture.read()
        if not ok or int(capture.get(cv2.CAP_PROP_POS_FRAMES)) != index + 1:
            raise ValueError("Native video frame support cannot be independently confirmed")
        input_key = int(input_keys[index])
        file = folder / f"video_{index:06d}_input_{input_key:06d}.png"
        if not cv2.imwrite(str(file), image):
            raise OSError("Unable to preserve a decoded native example")
        examples.append({"video_frame": index, "original_input_key": input_key,
                         "file": str(file), "sha256": sha256(file), "height": image.shape[0], "width": image.shape[1]})
    capture.release()
    source = PROJECT / "baselines/ba_track/upstream/main/slam_visualizer.py"
    for file in (source, Path(__file__), sequence_source, clip_source):
        shutil.copy2(file, folder / (file.name + ".reviewed_source"))
    record = {"status": "NATIVE_VIDEO_FIXED_EXAMPLES_DECODED_VISUAL_REVIEW_PENDING", "video": str(video),
              "video_sha256": sha256(video), "decoded_frame_count": count, "camera_evaluation_input_denominator": contract["expected_frames"],
              "native_display_crop": "wide_list[2:-1]; MoviePy float-duration scheduling may repeat the final selected image; primary camera support is unchanged",
              "encoded_fps": fps, "selected_distinct_input_images": len(selected_input_keys),
              "encoded_frame_to_original_input_key": input_keys.tolist(),
              "additional_encoded_frames_from_repeated_source_images": count-len(selected_input_keys),
              "moviepy_duration_float": float(sum([1.0 / fps] * len(selected_input_keys))),
              "moviepy_timing_sources": [{"file": str(p), "sha256": sha256(p)} for p in (sequence_source, clip_source)],
              "layout": "Author concatenates res_video_sta above res_video_dyn along image height; colors/tracks are native predictions, not independent motion labels",
              "fixed_selection": "First, middle and last encoded frame, chosen before viewing; no GT or model replay",
              "opencv_version": cv2.__version__, "native_renderer_source_sha256": sha256(source),
              "inspection_source_sha256": sha256(Path(__file__)), "examples": examples, "figures_visually_reviewed": False}
    write_json(folder / "selection.json", record)
    print({"status": record["status"], "video_frames": count, "directory": str(folder)})


if __name__ == "__main__":
    main()
