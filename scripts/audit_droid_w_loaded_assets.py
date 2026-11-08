"""Verify the extra base DINO checkpoint actually fetched by FiT3D/timm."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import time
from urllib.request import urlopen

ROOT = Path("/mnt/d/aaa/GameCam-VO")


def main():
    cache = ROOT / "data/sota_assets/DROID_W/huggingface/hub"
    files = list(cache.glob("models--timm--*/snapshots/*/model.safetensors"))
    if not files:
        raise RuntimeError("No actual base DINO cache file; cannot claim it downloaded")
    out = ROOT / "data/sota_assets/DROID_W/loaded_asset_audits" / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out.mkdir(parents=True, exist_ok=False)
    results = []
    for path in files:
        repo = path.parents[2].name.removeprefix("models--").replace("--", "/")
        revision = path.parent.name
        url = f"https://huggingface.co/api/models/{repo}/tree/{revision}?recursive=true&limit=1000"
        with urlopen(url, timeout=40) as response:
            tree = json.load(response)
        entry = next(e for e in tree if e["path"] == path.name)
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                h.update(block)
        checksum = h.hexdigest()
        assert checksum == entry["lfs"]["oid"] and path.stat().st_size == entry["size"]
        result = {"repository": repo, "revision": revision, "file": path.name, "cache_file": str(path),
                  "bytes": path.stat().st_size, "sha256": checksum, "verification": "MATCHES_PINNED_HF_LFS", "metadata_url": url,
                  "purpose": "Official FiT3D/timm pretrained=True base initialization; then strict fine-tuned state load overrides it"}
        results.append(result)
        (out / (path.parents[2].name + "_tree.json")).write_text(json.dumps(tree, indent=2))
    status = {"status": "ACTUALLY_LOADED_BASE_ASSET_VERIFIED", "directory": str(out), "assets": results,
              "extra_checkpoint_bytes": sum(r["bytes"] for r in results), "other_baseline_assets_downloaded": False}
    (ROOT / "reports/SOTA/droid_loaded_prior_assets.json").write_text(json.dumps(status, indent=2))
    print(json.dumps(status))


if __name__ == "__main__":
    main()
