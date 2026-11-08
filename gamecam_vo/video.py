from __future__ import annotations

from pathlib import Path
import av
import cv2
import numpy as np


def probe_video(path: str | Path) -> dict:
    with av.open(str(path)) as container:
        if not container.streams.video:
            raise ValueError("No video stream")
        stream = container.streams.video[0]
        fps = float(stream.average_rate) if stream.average_rate else None
        duration = float(stream.duration * stream.time_base) if stream.duration is not None else (
            container.duration / av.time_base if container.duration is not None else None)
        return {"path": str(Path(path).resolve()), "width": stream.width, "height": stream.height,
                "fps": fps, "frame_count_metadata": stream.frames or None,
                "duration_seconds": duration, "time_base": str(stream.time_base),
                "start_pts_seconds": float(stream.start_time * stream.time_base) if stream.start_time is not None else None,
                "codec": stream.codec_context.name, "frame_count_source": "container_metadata_not_full_decode"}


def iter_frames(path: str | Path, clip: dict, resize_width: int | None = None):
    start, duration = float(clip["start_seconds"]), float(clip["duration_seconds"])
    stride = int(clip["frame_stride"])
    if start < 0 or duration <= 0 or stride < 1:
        raise ValueError("Invalid clip sampling configuration")
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        first_pts = None
        sample_index = 0
        for frame_index, frame in enumerate(container.decode(stream)):
            if frame.pts is None or frame.time_base is None:
                raise ValueError("Missing video presentation timestamps")
            pts = float(frame.pts * frame.time_base)
            first_pts = pts if first_pts is None else first_pts
            relative = pts - first_pts
            if relative + 1e-9 < start:
                continue
            if relative >= start + duration - 1e-9:
                break
            keep = sample_index % stride == 0
            sample_index += 1
            if not keep:
                continue
            image = frame.to_ndarray(format="bgr24")
            original_height, original_width = image.shape[:2]
            if resize_width and original_width > resize_width:
                height = max(1, round(original_height * resize_width / original_width))
                image = cv2.resize(image, (resize_width, height), interpolation=cv2.INTER_AREA)
            yield {"frame_index": frame_index, "video_pts_seconds": pts,
                   "video_relative_seconds": relative, "image": image,
                   "scale_x": image.shape[1] / original_width, "scale_y": image.shape[0] / original_height}


def intrinsic_matrix(values: np.ndarray, scale_x: float = 1.0, scale_y: float = 1.0) -> np.ndarray:
    values = np.asarray(values, float)
    if values.shape == (3, 3):
        if not np.allclose(values[2], [0, 0, 1]) or not np.allclose([values[0, 1], values[1, 0]], 0):
            raise ValueError("Only the documented zero-skew pinhole camera is supported")
        fx, fy, cx, cy = values[0, 0], values[1, 1], values[0, 2], values[1, 2]
    elif values.shape == (4,):
        fx, fy, cx, cy = values
    else:
        raise ValueError("Intrinsics must be a 3x3 K matrix or (fx, fy, cx, cy)")
    # cv2.resize uses pixel-center coordinates: dst=(src+0.5)*scale-0.5.
    return np.array([[fx * scale_x, 0, (cx + 0.5) * scale_x - 0.5],
                     [0, fy * scale_y, (cy + 0.5) * scale_y - 0.5], [0, 0, 1]])
