"""Run the original Pi_SAM/DPVO pipeline with opt-in IO-only observation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import numpy as np
import torch
import torch.multiprocessing as mp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "baselines/pi3mos/upstream"))
import demo as native
from dpvo.dpvo import DPVO as OriginalDPVO


def log_json(path, row):
    with path.open("a") as stream:
        stream.write(json.dumps(row)+"\n")


def save_arrays(path, values):
    arrays, dtypes = {}, {}
    for key, value in values.items():
        tensor = value.detach().cpu()
        dtypes[key] = str(tensor.dtype)
        # NumPy has no native bfloat16. This IO conversion preserves its values
        # exactly and never changes the tensor consumed by the model.
        arrays[key] = (tensor.float() if tensor.dtype == torch.bfloat16 else tensor).numpy()
    np.savez_compressed(path, **arrays)
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest() if sys.version_info >= (3, 11) else None
    if digest is None:
        value = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(4*1024*1024), b""):
                value.update(block)
        digest = value.hexdigest()
    return {"file": path.name, "sha256": digest, "native_torch_dtypes": dtypes,
            "shapes": {key: list(value.shape) for key, value in arrays.items()},
            "all_values_finite": all(np.isfinite(value).all() for value in arrays.values()),
            "bfloat16_to_float32_is_io_only_if_needed": True}


class ObservedDPVO(OriginalDPVO):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.observation_out = Path(os.environ["GAMECAM_PI3MOS_RUN_DIR"])
        self.prior_counter = 0
        self.current_input_index = None

    def initialization(self):
        folder = self.observation_out / "raw_initialization"
        folder.mkdir(exist_ok=True)
        observed = []

        def record(module, inputs, output):
            selected = {key: output[key] for key in ("local_points", "conf", "camera_poses", "dynamic_masks")}
            row = save_arrays(folder / f"model_forward_{len(observed):04d}.npz", selected)
            row.update(input_frame_indices=list(self.tlist), current_input_index=self.current_input_index,
                       coordinate_scope="Unmodified native model output before DPVO scale alignment", observer_returned_None=True)
            observed.append(row)
            log_json(folder / "manifest.jsonl", row)

        handle = self.pi3.register_forward_hook(record)
        try:
            return super().initialization()
        finally:
            handle.remove()

    def pi3_inference(self, id_list):
        result = super().pi3_inference(id_list)
        folder = self.observation_out / "native_prior_outputs"
        folder.mkdir(exist_ok=True)
        row = save_arrays(folder / f"input_{self.current_input_index:05d}.npz", {
            "local_points_scaled_current": result[1][-1], "depth_prior_fmap_current": result[2][-1],
            "confidence_fmap_current": result[3][-1], "dynamic_probability_fmap_current": result[4][-1],
            "aligned_prior_T_cw_window": result[0]})
        input_ids = [self.current_input_index if i == self.n else int(self.pg.tstamps_[i]) for i in id_list]
        row.update(current_input_index=self.current_input_index, native_retained_window_ids=list(id_list),
                   window_input_indices=input_ids, original_method_called_once_return_unchanged=True,
                   local_point_depth_scale="Native DPVO-aligned learned prior unit; no asserted game metric conversion",
                   fmap_resolution="Native feature-map grid used by the tracker; not interpolated to full RGB")
        log_json(folder / "manifest.jsonl", row)
        self.prior_counter += 1
        return result

    def __call__(self, tstamp, image, intrinsics=None):
        self.current_input_index = int(tstamp)
        initialized_before = bool(self.is_initialized)
        started = time.monotonic()
        result = super().__call__(tstamp, image, intrinsics)
        row = {"input_frame_index": self.current_input_index, "input_timestamp": float(tstamp),
               "initialized_before": initialized_before, "initialized_after": bool(self.is_initialized),
               "retained_keyframes": self.n, "input_image_shape": list(image.shape),
               "native_call_including_observation_seconds": time.monotonic()-started,
               "native_counter": self.counter, "current_prior_provided": result[0] is not None}
        log_json(self.observation_out / "frontend_frames.jsonl", row)
        print(json.dumps(row), flush=True)
        return result

    def terminate(self):
        poses, timestamps = super().terminate()
        out = self.observation_out
        np.save(out / "native_poses_T_wc_xyzw.npy", poses)
        np.save(out / "native_timestamps.npy", timestamps)
        np.savetxt(out / "native_full_trajectory_tum.txt", np.column_stack([timestamps, poses]), fmt="%.12g",
                   header="Native DPVO terminate(): T_wc, XYZW; frame-index timestamps")
        np.savez_compressed(out / "native_final_keyframes.npz", poses_T_cw=self.pg.poses_[:self.n].detach().cpu().numpy(),
                            input_frame_indices=np.asarray(self.pg.tstamps_[:self.n]), intrinsics_feature_grid=self.pg.intrinsics_[:self.n].detach().cpu().numpy())
        return poses, timestamps


class HeadlessPiSAM(native.Pi_SAM):
    def __init__(self, config):
        super().__init__(config)
        # Isolated execution of the original method reproduced AttributeError
        # when --viz is absent. Supply only its omitted optional GUI handle.
        if not hasattr(self, "gui_process"):
            self.gui_process = None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--imagedir", required=True)
    parser.add_argument("--calib", required=True)
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    os.environ["GAMECAM_PI3MOS_RUN_DIR"] = str(args.outdir)
    native.cfg.merge_from_file(args.config)
    (args.outdir / "native_resolved_config.yaml").write_text(native.cfg.dump())
    native.DPVO = ObservedDPVO
    config = {"imagedir": args.imagedir, "calib": args.calib, "stride": 1, "viz": False, "tum": False, "edge": 0, "gt": None}
    runner = HeadlessPiSAM(config)
    try:
        runner.run()
    except BaseException:
        # These are only this dedicated process's image-reader/GUI children.
        # Avoid multiprocessing teardown hanging after an actual model failure.
        for child in mp.active_children():
            child.terminate()
            child.join(timeout=5)
        raise
    (args.outdir / "native_run_completed.json").write_text(json.dumps({"status": "NATIVE_PIPELINE_RETURNED", "original_run_method_used": True,
        "GT_argument": None, "original_model_parameters_preserved": True, "optional_GUI_omitted": True}))


if __name__ == "__main__":
    main()
