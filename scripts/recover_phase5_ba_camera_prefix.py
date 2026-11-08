"""Recover complete native camera fields from an interrupted local pickle prefix.

No model rerun and no fabricated/repaired numeric values. Large track payloads
are never read into memory. The failed native pipeline remains failed.
"""
from __future__ import annotations

import _bootstrap
import argparse
import json
from pathlib import Path
import pickle
import shutil
import sys

import numpy as np
from scipy.spatial.transform import Rotation

from gamecam_vo.common import PROJECT, sha256, write_json
from phase5_motion_support import read, json_lines
from export_ba_track_results import validate_camera


class PrefixLimit(Exception):
    pass


class BoundedReader:
    def __init__(self, stream, limit=2*1024**2):
        self.stream, self.limit = stream, limit
        self.largest_requested_read = 0

    def read(self, n=-1):
        self.largest_requested_read = max(self.largest_requested_read, n)
        if n < 0 or self.stream.tell()+n > self.limit:
            raise PrefixLimit("Stopped before a large non-camera payload")
        return self.stream.read(n)

    def readline(self):
        remaining = self.limit-self.stream.tell()
        if remaining <= 0:
            raise PrefixLimit("Prefix byte limit reached")
        return self.stream.readline(remaining)


class NativeNumpyPrefix(pickle._Unpickler):
    def find_class(self, module, name):
        allowed = {("numpy", "ndarray"), ("numpy", "dtype"), ("numpy.core.multiarray", "_reconstruct"), ("numpy._core.multiarray", "_reconstruct")}
        if (module, name) not in allowed:
            raise pickle.UnpicklingError("Unexpected global in this native NumPy-only prefix: "+module+"."+name)
        return super().find_class(module, name)


def recover_prefix(path):
    with path.open("rb") as stream:
        reader = BoundedReader(stream)
        decoder = NativeNumpyPrefix(reader)
        try:
            decoder.load()
        except PrefixLimit as error:
            stop = str(error)
        else:
            raise ValueError("Expected an interrupted large native stream; use the full exporter for a complete pickle")
        stacks = [*decoder.metastack, decoder.stack]
        candidates = []
        for stack in stacks:
            for i in range(len(stack)-6):
                if (isinstance(stack[i], str) and stack[i] == "cams_T_world" and isinstance(stack[i+1], np.ndarray)
                    and isinstance(stack[i+2], str) and stack[i+2] == "intrinsics" and isinstance(stack[i+3], np.ndarray)
                    and isinstance(stack[i+4], str) and stack[i+4] == "tstamps" and isinstance(stack[i+5], np.ndarray)
                    and isinstance(stack[i+6], str) and stack[i+6] == "trajs_2d_disp"):
                    candidates.append({"cams_T_world": stack[i+1].copy(), "intrinsics": stack[i+3].copy(), "tstamps": stack[i+5].copy()})
        if len(candidates) != 1:
            raise ValueError("The exact first three complete native dictionary fields were not uniquely recovered")
        return candidates[0], {"stop": stop, "actual_file_prefix_bytes_read": stream.tell(), "maximum_prefix_bytes": reader.limit,
            "largest_read_request_refused_or_seen": reader.largest_requested_read,
            "field_order": ["cams_T_world", "intrinsics", "tstamps", "trajs_2d_disp (not loaded)"],
            "parser": "Bounded CPython pure-Python Unpickler; NumPy globals allowlisted; capture completed dictionary-value stack before large track payload"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    out = args.directory.resolve()
    if not out.is_relative_to(PROJECT / "results/E14_WILD_DYNAMIC/BA_TRACK"):
        raise ValueError("Only the diagnosed owned new local BA run is accepted")
    status, contract = read(out / "status.json"), read(out / "execution_contract.json")
    stages = status["stages"]
    if status["status"] != "BA_TRACK_PIPELINE_FAILED" or stages[-1]["stage"] != "sparse_tracker_and_BA" or stages[-1]["exit_code"] != -9:
        raise ValueError("This recovery is only for the observed native serialization SIGKILL")
    source = out / "upstream_output" / contract["scene"] / "results.pkl"
    target = out / "native_camera_prefix_recovery"
    if target.exists():
        raise FileExistsError("Preserve the previous recovery attempt")
    arrays, parse_review = recover_prefix(source)
    expected = contract["expected_frames"]
    times, poses, rigid = validate_camera(arrays["tstamps"], arrays["cams_T_world"], expected)
    if arrays["intrinsics"].shape != (expected, 4) or not np.isfinite(arrays["intrinsics"]).all():
        raise ValueError("Recovered complete camera intrinsics do not match all inputs")
    trace = json_lines(out / "motion_decomposition/frontend_calls.jsonl")
    if len(trace) != expected or [r["input_timestamp"] for r in trace] != list(range(expected)):
        raise ValueError("Actual completed frontend calls do not cover every input")
    context = trace[-1]
    if not context["online_camera_pose_support_matches_observed_images"]:
        raise ValueError("No independently archived last native camera states")
    indices = np.asarray(context["observed_window_input_indices"])
    if not np.array_equal(indices, indices.astype(int)):
        raise ValueError("Online observed frame keys are not integral")
    indices = indices.astype(int)
    w2c = np.asarray(context["online_window_poses_T_cw_xyzw"])
    matrices = np.broadcast_to(np.eye(4), (len(w2c), 4, 4)).copy()
    matrices[:, :3, :3] = Rotation.from_quat(w2c[:, 3:]).as_matrix()
    matrices[:, :3, 3] = w2c[:, :3]
    independently_observed_twc = np.linalg.inv(matrices)
    difference_t = np.linalg.norm(independently_observed_twc[:, :3, 3]-poses[indices, :3, 3], axis=1)
    difference_r = np.degrees(Rotation.from_matrix(np.swapaxes(independently_observed_twc[:, :3, :3], 1, 2) @ poses[indices, :3, :3]).magnitude())
    if difference_t.max() > 1e-4 or difference_r.max() > .01:
        raise ValueError("Recovered final camera direction/state disagrees with archived native online W2C states")
    target.mkdir(exist_ok=False)
    archive = target / "complete_native_camera_fields.npz"
    np.savez_compressed(archive, **arrays)
    source_code = PROJECT / "baselines/ba_track/upstream/main/batrack.py"
    shutil.copy2(source_code, target / "batrack.py.source_for_serializer_and_pose_direction")
    report = {"status": "COMPLETE_NATIVE_FINAL_SPARSE_CAMERA_PREFIX_RECOVERED_AND_INDEPENDENTLY_CHECKED",
        "native_pipeline_status_preserved": status["status"], "native_sparse_process_exit": -9, "full_pipeline_success_claim": False,
        "model_replayed": False, "GT_used_in_recovery_or_direction_choice": False, "native_numeric_values_modified": False,
        "expected_frames": expected, "complete_camera_frames": len(poses), "rigid_camera_checks": rigid,
        "raw_interrupted_pickle": str(source), "raw_interrupted_pickle_bytes": source.stat().st_size, "raw_interrupted_pickle_sha256": sha256(source),
        "complete_camera_archive": str(archive), "complete_camera_archive_sha256": sha256(archive), "bounded_parser": parse_review,
        "independent_native_state_comparison": {"frames": indices.tolist(), "max_translation_difference_native_unit": float(difference_t.max()),
            "max_rotation_difference_degrees": float(difference_r.max()), "online_trace_sha256": sha256(out / "motion_decomposition/frontend_calls.jsonl")},
        "source_direction": "Native get_results uses get_pose over every input then SE3.inv().matrix(); terminate performs no subsequent optimization before get_results",
        "serializer_source_sha256": sha256(source_code), "parser_source_sha256": sha256(Path(__file__)), "CPU_python": sys.version,
        "dense_refinement_or_full_track_pickle_recovered": False,
        "scientific_scope": "Only complete native final sparse camera fields and their support; large truncated track/depth/RGB payloads are not reconstructed"}
    shutil.copy2(__file__, target / "recover_phase5_ba_camera_prefix.py.executed_source")
    write_json(target / "recovery_review.json", report)
    print(json.dumps({"status": report["status"], "frames": len(poses), "prefix_read_bytes": parse_review["actual_file_prefix_bytes_read"],
        "independent_translation_max": float(difference_t.max()), "independent_rotation_max_degrees": float(difference_r.max()), "directory": str(target)}))


if __name__ == "__main__":
    main()
