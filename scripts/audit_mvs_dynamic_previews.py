"""Bounded appearance screening of four other sequences; no new evaluation set."""
from __future__ import annotations
import _bootstrap
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from urllib.request import urlopen

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from gamecam_vo.common import PROJECT, make_run_dir, write_json


def main():
    revision = "c886d86505054f18f79d0a1c838150d9e98935b2"
    slug = "fantasticoven/mvs-synth"
    sequences, frames = ["0001", "0039", "0079", "0119"], [0, 49, 99]
    out = make_run_dir(PROJECT / "data/mvs_synth/_dynamic_preview_audit", "four_sequence_screening")
    selected = []
    for sequence in sequences:
        url = f"https://huggingface.co/api/datasets/{slug}/tree/{revision}/GTAV_540/{sequence}/images?recursive=false&limit=1000"
        with urlopen(url, timeout=35) as response:
            tree = json.load(response)
        write_json(out / f"{sequence}_metadata.json", tree)
        for frame in frames:
            entry = next(e for e in tree if e["path"].endswith(f"/{frame:04d}.png"))
            selected.append({**entry, "sequence": sequence, "frame": frame})
    budget = 16 * 1024 * 1024
    if sum(e["size"] for e in selected) > budget or any(e["size"] > 2 * 1024 * 1024 for e in selected):
        raise ValueError("Bounded preview budget exceeded before image download")

    def fetch(entry):
        url = f"https://huggingface.co/datasets/{slug}/resolve/{revision}/{entry['path']}?download=true"
        with urlopen(url, timeout=60) as response:
            body = response.read(entry["size"] + 1)
        if len(body) != entry["size"]:
            raise ValueError("Unexpected preview size")
        sha = hashlib.sha256(body).hexdigest()
        verified = sha == entry["lfs"]["oid"] if entry.get("lfs") else hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest() == entry["oid"]
        if not verified:
            raise ValueError("Preview does not match the pinned mirror object")
        path = out / entry["sequence"] / f"{entry['frame']:04d}.png"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(body)
        return {"sequence": entry["sequence"], "frame": entry["frame"], "path": str(path), "url": url,
                "bytes": len(body), "sha256": sha, "mirror_object_verified": True, "independently_matched_official_archive": False}

    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(fetch, selected))
    fig, axes = plt.subplots(4, 3, figsize=(15, 11.6), layout="constrained")
    for ax, record in zip(axes.flat, records, strict=True):
        image = cv2.imread(record["path"])
        if image is None:
            raise ValueError("Preview RGB decode failed")
        ax.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        ax.set_title(f"Sequence {record['sequence']} / frame {record['frame']:04d}", fontsize=11)
        ax.set_axis_off()
    fig.suptitle("MVS-Synth: bounded appearance screening\nThree RGB frames per sequence do not establish independent object motion", fontsize=14)
    figure = out / "preview_contact_sheet.png"
    fig.savefig(figure, dpi=130)
    plt.close(fig)
    status = {"status": "BOUNDED_PREVIEWS_DOWNLOADED", "directory": str(out), "figure": str(figure),
              "mirror_repository": slug, "mirror_revision": revision, "sequences": sequences, "frame_indices": frames,
              "image_count": len(records), "total_network_rgb_bytes": sum(r["bytes"] for r in records), "budget_bytes": budget,
              "selection": "Evenly spread sequence indices selected before seeing images; frames 0,49,99. Existing approved mirror preference retained for phase4's requested other-sequence audit.",
              "official_independent_crosscheck_for_these_images": False,
              "dynamic_motion_ground_truth": "UNAVAILABLE", "usable_for_evaluation": False,
              "primary_MVS0000_data_or_configuration_changed": False, "records": records}
    write_json(out / "manifest.json", status)
    write_json(PROJECT / "reports/SOTA/mvs_dynamic_preview_audit.json", status)
    print(json.dumps({k: status[k] for k in ("status", "directory", "figure", "image_count", "total_network_rgb_bytes")}))


if __name__ == "__main__":
    main()
