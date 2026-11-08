"""Linux-side, selected-method-only asset acquisition after native CUDA proof."""
from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
import json
import subprocess
import time
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path("/mnt/d/aaa/GameCam-VO")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def download_bonn_chunks(item, log_dir):
    target, size = item["path"], item["size"]
    prefix = target.with_name(target.name + ".part")
    parts = target.with_name(target.name + ".parts")
    parts.mkdir(exist_ok=True)
    chunk_size = 8 * 1024 * 1024

    def fetch(index):
        start = index * chunk_size
        end = min(size, start + chunk_size) - 1
        count = end - start + 1
        part = parts / f"{index:04d}.part"
        reused = part.exists() and part.stat().st_size == count
        if not reused and prefix.exists() and prefix.stat().st_size >= end + 1:
            with prefix.open("rb") as existing:
                existing.seek(start)
                part.write_bytes(existing.read(count))
            reused = True
        if not reused:
            request_url = item["url"] + f"?gamecam_chunk={start}"
            for attempt in range(1, 4):
                try:
                    request = Request(request_url, headers={"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"})
                    with urlopen(request, timeout=180) as response:
                        if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{size}":
                            raise ValueError("Server did not honor the exact range")
                        body = response.read(count + 1)
                    if len(body) != count:
                        raise ValueError("Incomplete range")
                    part.write_bytes(body)
                    break
                except Exception:
                    if attempt == 3:
                        raise
                    time.sleep(1)
        row = {"index": index, "start": start, "end": end, "bytes": count, "sha256": digest(part), "reused_prefix_or_chunk": reused}
        print(json.dumps({"bonn_chunk_completed": index}), flush=True)
        return row

    with ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(fetch, range((size + chunk_size - 1) // chunk_size)))
    (log_dir / "bonn_chunk_manifest.json").write_text(json.dumps(records, indent=2))
    assembled = target.with_name(target.name + ".parallel.assembling")
    with assembled.open("wb") as output:
        for index in range(len(records)):
            with (parts / f"{index:04d}.part").open("rb") as part:
                for block in iter(lambda: part.read(8 * 1024 * 1024), b""):
                    output.write(block)
    assert assembled.stat().st_size == size
    with zipfile.ZipFile(assembled) as archive:
        assert archive.testzip() is None
    return assembled


def main():
    evidence = json.loads((ROOT / "reports/SOTA/latest_E7.json").read_text())["directory"]
    prior = ROOT / Path(evidence.replace("\\", "/").split("GameCam-VO/")[1]) / "prior_assets"
    native = json.loads((ROOT / "reports/SOTA/droid_native_probe.json").read_text())
    if native["status"] != "NATIVE_CUDA_CHECKS_PASSED":
        raise RuntimeError("No model acquisition before native CUDA checks pass")
    assets = ROOT / "data/sota_assets/DROID_W"
    checkpoints = assets / "torch_home/hub/checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)
    items = [
        {"name": "droid.pth", "path": assets / "weights/droid.pth", "size": 16061701,
         "url": "https://drive.usercontent.google.com/download?id=1PpqVt1H4maBa_GbPJp4NwxRsd9jk-elh&export=download&confirm=t"},
    ]
    for label, slug, revision, name in [
        ("metric3d", "JUGGHM/Metric3D", "80d2d1410afb4b23cd9d18c6be9144483d4b70b6", "metric_depth_vit_large_800k.pth"),
        ("fit3d", "yuanwenyue/FiT3D", "f52f1f99818cc15718933d3fe6d4bef4d96ada78", "dinov2_reg_small_finetuned.pth"),
    ]:
        tree = json.loads((prior / (label + "_tree.json")).read_text())
        entry = next(e for e in tree if e["path"] == name)
        items.append({"name": name, "path": checkpoints / name, "size": entry["size"],
                      "expected_sha256": entry["lfs"]["oid"], "revision": revision,
                      "url": f"https://huggingface.co/{slug}/resolve/{revision}/{name}?download=true"})
    items.append({"name": "rgbd_bonn_balloon.zip", "path": assets / "downloads/rgbd_bonn_balloon.zip", "size": 243818512,
                  "url": "https://www.ipb.uni-bonn.de/html/projects/rgbd_dynamic2019/rgbd_bonn_balloon.zip"})
    attempt = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    log_dir = ROOT / "logs/SOTA_setup" / (attempt + "_droid_assets")
    log_dir.mkdir(exist_ok=False)
    results = []
    for item in items:
        target = item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        row = {**item, "path": str(target)}
        if not target.exists():
            partial = target.with_name(target.name + ".part")
            if item["name"] == "rgbd_bonn_balloon.zip":
                partial = download_bonn_chunks(item, log_dir)
                row["transport"] = "6 bounded HTTP range workers; retained original prefix; exact Content-Range/size checks and full ZIP CRC"
            else:
                cmd = ["curl", "--fail", "--location", "--retry", "3", "--connect-timeout", "30", "--max-time", "1800", "--continue-at", "-", "--output", str(partial), item["url"]]
                row["command"] = cmd
                with (log_dir / (item["name"] + ".log")).open("w") as log:
                    process = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
                row["exit_code"] = process.returncode
                if process.returncode:
                    results.append(row)
                    (log_dir / "assets.json").write_text(json.dumps(results, indent=2))
                    raise RuntimeError(f"Asset transport failed: {item['name']}")
            if partial.stat().st_size != item["size"]:
                raise ValueError(f"Wrong full asset size: {partial.stat().st_size} != {item['size']}")
            checksum = digest(partial)
            if item.get("expected_sha256") and checksum != item["expected_sha256"]:
                raise ValueError(f"Full SHA256 mismatch: {item['name']}")
            partial.rename(target)
        row.update(actual_bytes=target.stat().st_size, sha256=digest(target))
        assert row["actual_bytes"] == item["size"]
        assert not item.get("expected_sha256") or row["sha256"] == item["expected_sha256"]
        row["verification"] = "SHA256_MATCHES_HF_LFS" if item.get("expected_sha256") else "FULL_SIZE_AND_LOCAL_SHA256; no publisher digest available"
        results.append(row)
        (log_dir / "assets.json").write_text(json.dumps(results, indent=2))
        print(json.dumps(row), flush=True)
    demo_root = assets / "demo"
    demo_root.mkdir(exist_ok=True)
    with zipfile.ZipFile(items[-1]["path"]) as archive:
        for name in archive.namelist():
            resolved = (demo_root / name).resolve()
            if not resolved.is_relative_to(demo_root.resolve()):
                raise ValueError("Unsafe archive member")
        if archive.testzip() is not None:
            raise ValueError("Official demo ZIP CRC failure")
        archive.extractall(demo_root)
    final = {"status": "DROID_ASSETS_VERIFIED", "directory": str(log_dir), "assets": results,
             "method": "DROID_W", "other_method_weights_downloaded": False,
             "base_dino_note": "FiT3D/timm additionally initializes a base DINO model. Capture its cache files and hashes at first load; it is not yet downloaded here.",
             "bonn_image_count": len(list(demo_root.rglob("rgb/*.png")))}
    (ROOT / "reports/SOTA/droid_assets.json").write_text(json.dumps(final, indent=2))


if __name__ == "__main__":
    main()
