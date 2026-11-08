"""Linux-side acquisition of BA-Track assets, gated on its native CUDA proof."""
from __future__ import annotations

import hashlib
import argparse
import json
import re
import shutil
import subprocess
import tarfile
import time
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path("/mnt/d/aaa/GameCam-VO")


def checksum(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hf-transport-base", choices=["https://huggingface.co", "https://hf-mirror.com"], default="https://huggingface.co")
    parser.add_argument("--hf-only", action="store_true", help="Acquire verified HF priors while independent Google Drive assets are network-blocked; never claim complete Demo readiness")
    parser.add_argument("--dino-only", action="store_true", help="Acquire the official DINO base initialization and pinned Hub source independently of Google Drive")
    args = parser.parse_args()
    if args.hf_only and args.dino_only:
        raise ValueError("Select one bounded asset group")
    native = json.loads((ROOT / "reports/SOTA/ba_track_native_probe.json").read_text())
    if native["status"] != "BA_TRACK_NATIVE_CUDA_CHECKS_PASSED":
        raise RuntimeError("Build and actual CUDA numerical checks must pass before acquiring BA-Track weights")
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = ROOT / "logs/SOTA_setup" / (stamp + "_ba_track_assets")
    out.mkdir(exist_ok=False)
    assets = ROOT / "data/sota_assets/BA_TRACK"
    assets.mkdir(parents=True, exist_ok=True)
    evidence = json.loads((ROOT / "reports/SOTA/latest_E7.json").read_text())["directory"]
    audit = ROOT / evidence.replace("\\", "/").split("GameCam-VO/")[-1] / "prior_assets"
    checkpoint_cache = assets / "torch_home/hub/checkpoints"
    uni_revision = "1d0d3c52f60b5164629d279bb9a7546458e6dcc4"
    da_revision = "cbbb86a30ce19b5684b7a05155dc7e6cbc7685b9"
    records = []
    try:
        git_metadata = assets / "metadata/depth_anything_v2_official_git"
        if git_metadata.is_dir():
            primary_metadata = json.loads((audit / "dav2_model.json").read_text())
            if primary_metadata["sha"] != da_revision:
                raise ValueError("The saved primary-source model revision changed")
            commit_bytes = subprocess.check_output(["git", "-C", str(git_metadata), "cat-file", "commit", da_revision])
            authenticated_commit = hashlib.sha1(b"commit " + str(len(commit_bytes)).encode() + b"\0" + commit_bytes).hexdigest()
            if authenticated_commit != da_revision:
                raise ValueError("Model metadata Git commit hash failed")
            pointer = subprocess.check_output(["git", "-C", str(git_metadata), "show", da_revision + ":depth_anything_v2_vitl.pth"])
            fields = dict(line.split(" ", 1) for line in pointer.decode().splitlines())
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", fields["oid"]):
                raise ValueError("Invalid Git-authenticated LFS pointer")
            da = {"size": int(fields["size"]), "lfs": {"oid": fields["oid"].split(":", 1)[1]}}
            (out / "dav2_git_lfs_provenance.json").write_text(json.dumps({"official_revision_from_primary_E7_metadata": da_revision,
                "authenticated_commit_sha1": authenticated_commit, "lfs_pointer": pointer.decode(), "metadata_transport": "hf-mirror.com Git fetch; exact commit object ID pinned from earlier official HF API",
                "full_weight_bytes_still_require_lfs_sha256_match": True}, indent=2))
        else:
            tree_url = f"https://huggingface.co/api/models/depth-anything/Depth-Anything-V2-Large/tree/{da_revision}?recursive=true&limit=1000"
            with urlopen(Request(tree_url, headers={"User-Agent": "GameCam-VO"}), timeout=60) as response:
                body = response.read(2 * 1024 * 1024 + 1)
            if len(body) > 2 * 1024 * 1024:
                raise ValueError("HF metadata cap exceeded")
            (out / "dav2_tree.json").write_bytes(body)
            da = next(row for row in json.loads(body) if row["path"] == "depth_anything_v2_vitl.pth")
        if da["size"] != 1341395338 or len(da["lfs"]["oid"]) != 64:
            raise ValueError("Unexpected pinned DA-V2 metadata")
        uni_tree = json.loads((audit / "unidepth_tree.json").read_text())
        uni_cache = assets / "huggingface/hub/models--lpiccinelli--unidepth-v2-vitl14/snapshots" / uni_revision
        items = [
            {"name": "md_tracker.pth", "path": assets / "weights/md_tracker.pth", "size": 423781410,
             "url": "https://drive.usercontent.google.com/download?id=1wWK_ur0Pr4jivqDUdyRUFzHPaF-f1clC&export=download&confirm=t"},
            {"name": "depth_anything_v2_vitl.pth", "path": assets / "weights/depth_anything_v2_vitl.pth", "size": da["size"],
             "expected_sha256": da["lfs"]["oid"], "revision": da_revision,
             "url": f"https://huggingface.co/depth-anything/Depth-Anything-V2-Large/resolve/{da_revision}/depth_anything_v2_vitl.pth?download=true"},
        ]
        for name in ("config.json", "model.safetensors"):
            entry = next(row for row in uni_tree if row["path"] == name)
            item = {"name": "unidepth_" + name, "path": uni_cache / name, "size": entry["size"], "revision": uni_revision,
                    "url": f"https://huggingface.co/lpiccinelli/unidepth-v2-vitl14/resolve/{uni_revision}/{name}?download=true"}
            if "lfs" in entry:
                item["expected_sha256"] = entry["lfs"]["oid"]
            else:
                item["expected_git_blob_sha1"] = entry["oid"]
            items.append(item)
        items += [
            {"name": "dino_deitsmall8_pretrain.pth", "path": checkpoint_cache / "dino_deitsmall8_pretrain.pth", "size": None,
             "maximum_bytes": 150 * 1024 * 1024,
             "url": "https://dl.fbaipublicfiles.com/dino/dino_deitsmall8_pretrain/dino_deitsmall8_pretrain.pth"},
            {"name": "davis.tar", "path": assets / "downloads/davis.tar", "size": 19046400,
             "url": "https://drive.usercontent.google.com/download?id=1hlHyxqW0AaPrv6NwJya0P2UJpcVNYbBU&export=download&confirm=t"},
        ]
        if args.hf_only:
            items = [item for item in items if item["url"].startswith("https://huggingface.co/")]
        elif args.dino_only:
            items = [item for item in items if item["name"] == "dino_deitsmall8_pretrain.pth"]
        for item in items:
            item["publisher_url"] = item["url"]
            if item["url"].startswith("https://huggingface.co/"):
                item["url"] = args.hf_transport_base + item["url"][len("https://huggingface.co"):]
            target = item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            row = {**item, "path": str(target)}
            if not target.exists():
                partial = target.with_name(target.name + ".part")
                command = ["curl", "--fail", "--location", "--retry", "2", "--connect-timeout", "30", "--max-time", "2400", "--continue-at", "-",
                           "--max-filesize", str(item["size"] or item["maximum_bytes"]), item["url"], "--output", str(partial)]
                row["command"] = command
                with (out / (item["name"] + ".log")).open("w") as log:
                    process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
                row["exit_code"] = process.returncode
                if process.returncode:
                    records.append(row)
                    raise RuntimeError(f"Download failed: {item['name']}; partial retained")
                if item["size"] and partial.stat().st_size != item["size"]:
                    raise ValueError(f"Wrong full size: {item['name']}")
                if item.get("expected_sha256") and checksum(partial) != item["expected_sha256"]:
                    raise ValueError(f"Pinned LFS checksum mismatch: {item['name']}")
                if item.get("expected_git_blob_sha1"):
                    contents = partial.read_bytes()
                    if hashlib.sha1(b"blob " + str(len(contents)).encode() + b"\0" + contents).hexdigest() != item["expected_git_blob_sha1"]:
                        raise ValueError("Pinned config Git blob mismatch")
                partial.rename(target)
            row.update(actual_bytes=target.stat().st_size, sha256=checksum(target))
            if item["name"] == "dino_deitsmall8_pretrain.pth":
                with target.open("rb") as stream:
                    prefix = stream.read(8)
                if row["actual_bytes"] < 64*1024*1024 or not (prefix.startswith(b"PK") or prefix.startswith(b"\x80")):
                    raise ValueError("Unexpected base DINO serialization/size")
            if item["size"] and row["actual_bytes"] != item["size"]:
                raise ValueError("Existing asset size mismatch")
            if item.get("expected_sha256") and row["sha256"] != item["expected_sha256"]:
                raise ValueError("Existing pinned model checksum mismatch")
            if item.get("expected_git_blob_sha1"):
                contents = target.read_bytes()
                if hashlib.sha1(b"blob " + str(len(contents)).encode() + b"\0" + contents).hexdigest() != item["expected_git_blob_sha1"]:
                    raise ValueError("Existing pinned config Git blob mismatch")
            row["verification"] = "FULL_SHA256_MATCHES_PINNED_HF_LFS" if item.get("expected_sha256") else "FULL_LOCAL_SHA256; publisher digest unavailable except config Git blob"
            records.append(row)
            (out / "assets.json").write_text(json.dumps(records, indent=2))
            print(json.dumps({"verified_asset": item["name"], "bytes": row["actual_bytes"], "sha256": row["sha256"]}), flush=True)
        if args.hf_only:
            record = {"status": "BA_TRACK_HF_PRIORS_VERIFIED_PARTIAL", "directory": str(out), "assets": records,
                      "still_required": ["Google_Drive_md_tracker.pth", "Google_Drive_DAVIS_demo", "base_DINO_checkpoint"],
                      "official_demo_ready": False, "model_inference_executed": False, "other_method_weights_downloaded": False}
            (out / "status.json").write_text(json.dumps(record, indent=2))
            (ROOT / "reports/SOTA/ba_track_hf_prior_assets.json").write_text(json.dumps(record, indent=2))
            print(json.dumps({"status": record["status"], "directory": str(out)}), flush=True)
            return 0
        # Freeze torch.hub's otherwise floating facebookresearch/dino:main
        # cache from the reviewed source commit, without editing model code.
        dino = ROOT / "baselines/ba_track/prior_sources/dino"
        pin = subprocess.check_output(["git", "-C", str(dino), "rev-parse", "HEAD"], text=True).strip()
        if pin != "7c446df5b9f45747937fb0d72314eb9f7b66930a":
            raise ValueError("DINO source pin changed")
        hub_cache = assets / "torch_home/hub/facebookresearch_dino_main"
        source_files = subprocess.check_output(["git", "-C", str(dino), "ls-files", "-z"]).decode().split("\0")
        source_records = []
        for name in filter(None, source_files):
            source, destination = dino / name, hub_cache / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            source_records.append({"relative_path": name, "sha256": checksum(destination)})
        (out / "dino_hub_source_manifest.json").write_text(json.dumps(source_records, indent=2))
        if args.dino_only:
            record = {"status": "BA_TRACK_DINO_BASE_VERIFIED_PARTIAL", "directory": str(out), "assets": records,
                      "dino_source_pin": pin, "official_demo_ready": False, "still_required": ["Google_Drive_Tracker", "Google_Drive_DAVIS_demo"],
                      "verification_scope": "Direct official Meta HTTPS transport, full serialization/size and local SHA256; no publisher digest available"}
            (out / "status.json").write_text(json.dumps(record, indent=2))
            (ROOT / "reports/SOTA/ba_track_dino_assets.json").write_text(json.dumps(record, indent=2))
            print(json.dumps({"status": record["status"], "directory": str(out)}), flush=True)
            return 0
        demo = assets / "demo"
        demo.mkdir(exist_ok=True)
        with tarfile.open(assets / "downloads/davis.tar") as archive:
            members = archive.getmembers()
            if sum(member.size for member in members) > 100 * 1024 * 1024:
                raise ValueError("Unexpected demo archive expansion")
            for member in members:
                destination = (demo / member.name).resolve()
                if not destination.is_relative_to(demo.resolve()) or not (member.isfile() or member.isdir()):
                    raise ValueError("Unsafe DAVIS archive member")
            for member in members:
                destination = demo / member.name
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as source, destination.open("wb") as target:
                        shutil.copyfileobj(source, target)
        tennis = [path for path in demo.rglob("tennis") if path.is_dir() and any(path.glob("*.jpg"))]
        if len(tennis) != 1:
            raise ValueError("Expected exactly one official tennis RGB directory")
        record = {"status": "BA_TRACK_PRIMARY_ASSETS_VERIFIED", "directory": str(out), "assets": records,
                  "official_demo_rgb_directory": str(tennis[0]), "official_demo_rgb_frames": len(list(tennis[0].glob("*.jpg"))),
                  "dino_source_pin": pin, "model_weights_total_bytes": sum(row["actual_bytes"] for row in records if row["name"] != "davis.tar" and row["name"] != "unidepth_config.json"),
                  "other_method_weights_downloaded": False, "implicit_assets_note": "Actual model loading still must be audited for any additional prior initialization downloads."}
    except Exception as exc:
        record = {"status": "BA_TRACK_ASSET_ACQUISITION_FAILED", "directory": str(out), "error": f"{type(exc).__name__}: {exc}", "assets_so_far": records}
    (out / "status.json").write_text(json.dumps(record, indent=2))
    (ROOT / "reports/SOTA/ba_track_assets.json").write_text(json.dumps(record, indent=2))
    print(json.dumps({"status": record["status"], "directory": str(out)}), flush=True)
    return int(record["status"] != "BA_TRACK_PRIMARY_ASSETS_VERIFIED")


if __name__ == "__main__":
    raise SystemExit(main())
