"""Optional observation of official BA-Track, preserving all model return values."""
from __future__ import annotations

import json
import os
from pathlib import Path

from ba_track_motion_trace import attach_motion_trace


def install_observer(directory):
    import main.batrack as backend
    original = backend.BATRACK
    directory = Path(directory)

    class ObservedBATRACK(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if os.environ.get("GAMECAM_BA_VIDEO_VISIBILITY_CPU_COPY") == "1":
                from ba_track_video_io import install_video_visibility_copy
                install_video_visibility_copy(self.visualizer, directory)
            self._gamecam_image_input_indices = {}
            self._gamecam_hook = attach_motion_trace(self.network, directory / "raw", self._gamecam_context)

        def _gamecam_context(self):
            start = max(0, self.n - len(self.local_window))
            native_indices = self.tstamps_[:self.n].tolist()
            observed = [self._gamecam_image_input_indices.get(id(image)) for image in self.local_window]
            lookup = {float(value): index for index, value in enumerate(native_indices)}
            pose_indices = [lookup.get(value) for value in observed]
            complete = all(value is not None for value in pose_indices)
            row = {"retained_buffer_size": self.n, "input_calls_seen": self.counter,
                    "retained_window_input_indices": self.tstamps_[start:self.n].tolist(),
                    "observed_window_input_indices": observed,
                    "input_indices_observed_from_original_image_tensor_identity": True,
                    "all_input_timestamps_seen": [float(t) for t in self.tlist],
                    "online_camera_pose_support_matches_observed_images": complete,
                    "native_network_direction": "forward" if self.S_slam == self.cfg.model.S else "unverified_multiple_directions",
                    "native_input_image_shape": list(self.local_window[-1].shape) if self.local_window else None}
            if complete:
                row["online_window_poses_T_cw_xyzw"] = self.poses_[pose_indices].detach().cpu().numpy().tolist()
                row["online_window_intrinsics_fx_fy_cx_cy"] = self.intrinsics_[pose_indices].detach().cpu().numpy().tolist()
                row["pose_intrinsics_scope"] = "Actual native buffer states when context was observed; not final BA poses; no GT used"
            return row

        def __call__(self, *args, **kwargs):
            self._gamecam_image_input_indices[id(args[1])] = float(args[0])
            result = super().__call__(*args, **kwargs)
            context = self._gamecam_context()
            context["input_timestamp"] = float(args[0])
            context["initialized"] = bool(self.is_initialized)
            with (directory / "frontend_calls.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(context) + "\n")
            return result

        def terminate(self):
            result = super().terminate()
            if os.environ.get("GAMECAM_BA_SAVE_TERMINATED_CAMERA") == "1":
                import hashlib
                import numpy as np
                try:
                    # Native terminate returns T_wc translation + WXYZ and
                    # sample keys. This optional archive does not modify them.
                    poses, indices = result
                    file = directory / "native_terminated_camera.npz"
                    np.savez_compressed(file, native_T_wc_translation_quaternion_WXYZ=poses, native_input_indices=indices,
                        final_retained_T_cw_translation_quaternion_XYZW=self.poses_[:self.n].detach().cpu().numpy(),
                        final_retained_input_indices=self.tstamps_[:self.n].detach().cpu().numpy())
                    (directory / "native_terminated_camera.json").write_text(json.dumps({"status": "NATIVE_TERMINATE_RETURN_ARCHIVED_BEFORE_LARGE_RESULT_SERIALIZATION",
                        "archive": str(file), "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "frames": len(indices),
                        "pose_convention": "Native returned T_wc, translation then WXYZ; retained internal states are T_cw translation then XYZW",
                        "original_terminate_called_once_return_unchanged": True, "extra_model_forwards": 0, "RNG_draws": 0,
                        "GT_used": False, "full_pipeline_success_claim": False}, indent=2)+"\n")
                except Exception as error:
                    # Failure of our optional recorder must not interrupt the
                    # original return or the author's later result/TUM writers.
                    # Native super().terminate() exceptions remain uncaught.
                    record = {"status": "OPTIONAL_CAMERA_ARCHIVE_FAILED_ORIGINAL_NATIVE_RETURN_PRESERVED",
                        "error_type": type(error).__name__, "error": str(error),
                        "original_terminate_called_once_return_unchanged": True, "GT_used": False}
                    try:
                        (directory / "native_terminated_camera_error.json").write_text(json.dumps(record, indent=2)+"\n")
                    except OSError:
                        pass
                    import sys
                    print(json.dumps(record), file=sys.stderr, flush=True)
            return result

    backend.BATRACK = ObservedBATRACK
