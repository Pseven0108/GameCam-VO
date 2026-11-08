"""CPU-only extraction of one verified official test record, no model inference."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from movi_tfrecord_io import decode_features


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("record", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Use a fresh extraction directory; preserve previous evidence")
    raw = args.record.read_bytes()
    features = decode_features(raw)
    t = int(features["metadata/num_frames"][0])
    h, w = int(features["metadata/height"][0]), int(features["metadata/width"][0])
    n = int(features["metadata/num_instances"][0])
    if (t, h, w) != (24, 256, 256) or n < 1:
        raise ValueError("The pinned MOVi-E test schema differs")
    arrays, schema = {}, {}
    def tensor(name, shape):
        value = np.asarray(features[name])
        if value.size != int(np.prod(shape)):
            raise ValueError("Official tensor shape mismatch: "+name)
        value = value.reshape(shape)
        if not np.isfinite(value).all():
            raise ValueError("Nonfinite official GT field: "+name)
        arrays[name.replace("/", "__")] = value
    for key, shape in (("positions", (t, 3)), ("quaternions", (t, 4)), ("focal_length", ()), ("sensor_width", ()), ("field_of_view", ())):
        tensor("camera/"+key, shape)
    for key, shape in (("positions", (n, t, 3)), ("quaternions", (n, t, 4)), ("velocities", (n, t, 3)), ("angular_velocities", (n, t, 3)),
        ("visibility", (n, t)), ("image_positions", (n, t, 2)), ("bboxes_3d", (n, t, 8, 3)), ("is_dynamic", (n,)), ("scale", (n,))):
        tensor("instances/"+key, shape)
    for key in ("depth_range", "forward_flow_range", "backward_flow_range"):
        tensor("metadata/"+key, (2,))
    for key in ("forward_flow", "backward_flow"):
        values = np.asarray(features[key])
        if values.min() < 0 or values.max() > 65535:
            raise ValueError("Flow quantization is not unsigned 16-bit")
        arrays[key] = values.astype(np.uint16).reshape(t, h, w, 2)
    for key, channels, dtype in (("video", 3, np.uint8), ("segmentations", 1, np.uint8), ("depth", 1, np.uint16),
        ("normal", 3, np.uint16), ("object_coordinates", 3, np.uint16)):
        encoded = features[key]
        if not isinstance(encoded, list) or len(encoded) != t:
            raise ValueError("Expected native TFDS per-frame encoded PNG sequence: "+key)
        images = []
        for frame in encoded:
            image = cv2.imdecode(np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            if image is None or image.shape[:2] != (h, w) or image.dtype != dtype:
                raise ValueError("Native PNG shape/dtype decoding failed: "+key)
            if channels == 3:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                image = image.reshape(h, w)
            images.append(image)
        arrays[key] = np.stack(images)
    if arrays["segmentations"].max() > n:
        raise ValueError("Instance IDs exceed official instance count")
    for key, values in features.items():
        schema[key] = {"wire_kind": "bytes_list" if isinstance(values, list) else "float_list" if values.dtype.kind == "f" else "int64_list", "elements": len(values),
            "decoded_shape": list(arrays[key.replace("/", "__")].shape) if key.replace("/", "__") in arrays else None}
    args.output.mkdir(parents=True, exist_ok=False)
    rgb = args.output / "rgb"
    rgb.mkdir()
    for index, image in enumerate(features["video"]):
        (rgb / f"{index:06d}.png").write_bytes(image)
    file = args.output / "sample_fields.npz"
    np.savez_compressed(file, **arrays)
    name = features["metadata/video_name"][0].decode("utf-8")
    record = {"status": "OFFICIAL_TEST_TFRECORD_EXTRACTED_CRC_VERIFIED", "video_name": name, "frames": t, "height": h, "width": w, "instances": n,
        "raw_record": str(args.record.resolve()), "raw_record_sha256": hashlib.sha256(raw).hexdigest(),
        "field_archive": str(file.resolve()), "field_archive_sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "fields": schema,
        "camera_quaternion_order": "WXYZ", "GT_provenance": "SYNTHETIC_GROUND_TRUTH", "unit": "Kubric_world_unit",
        "decoder": "Official TF Example wire field IDs via google.protobuf; PNG via cv2; no model inference or TensorFlow runtime"}
    (args.output / "extraction.json").write_text(json.dumps(record, indent=2)+"\n")
    print(json.dumps({k: record[k] for k in ("status", "video_name", "frames", "instances")}))


if __name__ == "__main__":
    main()
