"""Fixed hypothesis check: recoverPose's distant-point cutoff on measured matches."""
from __future__ import annotations
import _bootstrap
import json
import cv2
import numpy as np
from scipy.spatial.transform import Rotation

from datasets.registry import open_dataset
from gamecam_vo.common import PROJECT, make_run_dir, read_yaml, write_csv, write_json
from gamecam_vo.geometry import invert_se3
from gamecam_vo.orb import ratio_matches


def main():
    dataset = open_dataset(read_yaml(PROJECT / "configs/datasets/mvs_synth.yaml"))
    config = read_yaml(PROJECT / "configs/experiment.yaml")
    cv2.setRNGSeed(config["seed"])
    cv2.setNumThreads(config["opencv_threads"])
    extractor = cv2.ORB_create(nfeatures=config["orb"]["nfeatures"], scaleFactor=config["orb"]["scale_factor"],
                               nlevels=config["orb"]["nlevels"], fastThreshold=config["orb"]["fast_threshold"])
    matrices, poses = dataset.get_intrinsics(), dataset.get_poses()
    frames = {frame["frame_index"]: frame["image"] for frame in dataset.get_frames()}
    out = make_run_dir(PROJECT / "reports/diagnostics", "recover_pose_distance")
    rows = []
    for first, second in ((1, 2), (5, 6), (12, 13), (30, 31)):
        keypoints1, descriptors1 = extractor.detectAndCompute(cv2.cvtColor(frames[first], cv2.COLOR_BGR2GRAY), None)
        keypoints2, descriptors2 = extractor.detectAndCompute(cv2.cvtColor(frames[second], cv2.COLOR_BGR2GRAY), None)
        matches = ratio_matches(descriptors1, descriptors2, config["matching"]["lowe_ratio"])
        p1 = np.array([keypoints1[m.queryIdx].pt for m in matches], float).reshape(-1, 1, 2)
        p2 = np.array([keypoints2[m.trainIdx].pt for m in matches], float).reshape(-1, 1, 2)
        p1 = cv2.undistortPoints(p1, matrices[first], np.zeros(5)).reshape(-1, 2)
        p2 = cv2.undistortPoints(p2, matrices[second], np.zeros(5)).reshape(-1, 2)
        focal = np.mean([matrices[first, 0, 0], matrices[first, 1, 1], matrices[second, 0, 0], matrices[second, 1, 1]])
        essential, mask = cv2.findEssentialMat(p1, p2, np.eye(3), method=cv2.RANSAC,
            prob=config["ransac"]["confidence"], threshold=config["ransac"]["threshold_pixels"] / focal,
            maxIters=config["ransac"]["max_iterations"])
        truth = invert_se3(poses[second]) @ poses[first]
        for cutoff in (50.0, 1000.0):
            candidates = []
            for candidate in np.split(essential, essential.shape[0] // 3):
                values = cv2.recoverPose(candidate, p1, p2, np.eye(3), distanceThresh=cutoff, mask=mask.copy())
                count, rotation, translation, recovered, triangulated = values
                candidates.append((count, rotation, translation, recovered, triangulated))
            count, rotation, translation, recovered, triangulated = max(candidates, key=lambda item: item[0])
            inliers = recovered.ravel() != 0
            if inliers.any():
                rays1 = np.column_stack((p1[inliers], np.ones(inliers.sum())))
                rays2 = (rotation.T @ np.column_stack((p2[inliers], np.ones(inliers.sum()))).T).T
                rays1 /= np.linalg.norm(rays1, axis=1)[:, None]
                rays2 /= np.linalg.norm(rays2, axis=1)[:, None]
                angles = np.degrees(np.arccos(np.clip(np.sum(rays1 * rays2, axis=1), -1, 1)))
                depth = triangulated[2, inliers] / triangulated[3, inliers]
            else:
                angles, depth = [], []
            rows.append({"first_frame": first, "second_frame": second, "ratio_matches": len(matches),
                         "essential_ransac_inliers": int(mask.sum()), "distance_threshold_unit_baselines": cutoff,
                         "cheirality_inliers": int(count), "cheirality_inlier_ratio": count / len(matches),
                         "median_translation_parallax_degrees": float(np.median(angles)) if len(angles) else None,
                         "median_triangulated_depth_unit_baselines": float(np.median(depth)) if len(depth) else None,
                         "reference_rotation_error_degrees": float(np.degrees(Rotation.from_matrix(truth[:3, :3].T @ rotation).magnitude())),
                         "translation_direction_dot_reference": float(np.dot(translation.ravel(), truth[:3, 3] / np.linalg.norm(truth[:3, 3])))})
    write_csv(out / "distance_threshold_diagnosis.csv", rows)
    write_json(out / "protocol.json", {"pairs": [[1, 2], [5, 6], [12, 13], [30, 31]],
                "fixed_hypothesis": "The implicit distant-point limit can discard finite low-parallax geometry",
                "distance_thresholds": [50, 1000], "GT_used_to_select_E_or_pose": False,
                "pose_selection": "Maximum cheirality inliers only; reference error is measured afterwards",
                "no_trajectory_or_ATE_optimization": True})
    print(json.dumps({"out": str(out), "rows": rows}))


if __name__ == "__main__":
    main()
