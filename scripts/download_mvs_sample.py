from __future__ import annotations
import _bootstrap
import argparse
import json
from pathlib import Path, PurePosixPath

from gamecam_vo.acquisition import stream_extract
from gamecam_vo.common import PROJECT, make_run_dir, write_json


def main():
    parser = argparse.ArgumentParser(description="Retain ONE complete MVS-Synth sequence, never the full 10.5GB archive.")
    parser.add_argument("--sequence", default="0000")
    parser.add_argument("--max-download-mib", type=int, default=512)
    args = parser.parse_args()
    if args.sequence != "0000":
        raise ValueError("This first-sequence stream plan is limited to sequence 0000")
    if not 1 <= args.max_download_mib <= 512:
        raise ValueError("First sample compressed budget must be <=512 MiB")
    metadata = json.loads((PROJECT / "docs/sources/mvs_synth/repository_metadata.json").read_text(encoding="utf-8-sig"))
    revision = metadata["sha"]
    archive = f"https://huggingface.co/datasets/phuang17/MVS-Synth/resolve/{revision}/GTAV_540.tar.gz"
    destination = PROJECT / "data/mvs_synth/GTAV_540"
    run = make_run_dir(PROJECT / "logs/acquisition_mvs", "sequence_0000")
    expected = {f"0000/{kind}/{index:04d}.{extension}" for kind, extension in
                (("images", "png"), ("depths", "exr"), ("poses", "json")) for index in range(100)}
    def selector(path):
        parts = path.parts
        if len(parts) >= 3 and parts[-3] == "0000":
            relative = "/".join(parts[-3:])
            return PurePosixPath(relative) if relative in expected else None
        if parts[-1:] == ("num_images.json",):
            return PurePosixPath("num_images.json")
        return None
    write_json(run / "download_plan.json", {"dataset": "MVS-Synth", "revision": revision, "archive": archive,
               "selection": "One complete official GTA V sequence: 0000, 100 RGB + 100 EXR + 100 JSON",
               "license": "Research and educational use only; verified in official project and dataset card",
               "license_source": "https://phuang17.github.io/DeepMVS/mvs-synth.html",
               "method": "Sequential gzip/tar stream; disconnect immediately after all 300 selected members",
               "budget_bytes": args.max_download_mib * 1024**2, "destination": str(destination)})
    print(f"Plan saved: {run / 'download_plan.json'}", flush=True)
    result = stream_extract(archive, destination, selector, lambda selected: expected.issubset(selected),
                            args.max_download_mib * 1024**2, run / "download_manifest.json")
    print(json.dumps({"status": result["status"], "network_bytes_read": result["network_bytes_read"],
                      "selected_files": len(result["members"]), "manifest": str(run / "download_manifest.json")}))


if __name__ == "__main__":
    main()
