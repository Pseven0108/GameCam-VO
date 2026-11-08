from __future__ import annotations
import _bootstrap
import json
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from pathlib import Path
from gamecam_vo.common import PROJECT, write_json, sha256
from audit_sota_sources import bounded_probe


def main():
    out = Path(json.loads((PROJECT / "reports/SOTA/latest_E7.json").read_text())["directory"]) / "prior_assets"
    out.mkdir()
    urls = {
        "metric3d_hub.py": "https://raw.githubusercontent.com/YvanYin/Metric3D/main/hubconf.py",
        "metric3d_code_commit.json": "https://api.github.com/repos/YvanYin/Metric3D/commits/HEAD",
        "metric3d_model.json": "https://huggingface.co/api/models/JUGGHM/Metric3D",
        "metric3d_tree.json": "https://huggingface.co/api/models/JUGGHM/Metric3D/tree/main?recursive=true&limit=1000",
        "fit3d_hub.py": "https://raw.githubusercontent.com/ywyue/FiT3D/main/hubconf.py",
        "fit3d_code_commit.json": "https://api.github.com/repos/ywyue/FiT3D/commits/HEAD",
        "fit3d_model.json": "https://huggingface.co/api/models/yuanwenyue/FiT3D",
        "fit3d_tree.json": "https://huggingface.co/api/models/yuanwenyue/FiT3D/tree/main?recursive=true&limit=1000",
        "unidepth_model.json": "https://huggingface.co/api/models/lpiccinelli/unidepth-v2-vitl14",
        "unidepth_tree.json": "https://huggingface.co/api/models/lpiccinelli/unidepth-v2-vitl14/tree/1d0d3c52f60b5164629d279bb9a7546458e6dcc4?recursive=true&limit=1000",
        "dav2_model.json": "https://huggingface.co/api/models/depth-anything/Depth-Anything-V2-Large",
        "fit3d_README.md": "https://raw.githubusercontent.com/ywyue/FiT3D/main/README.md",
        "metric3d_README.md": "https://raw.githubusercontent.com/YvanYin/Metric3D/main/README.md",
    }
    def fetch(item):
        name, url = item
        try:
            with urlopen(Request(url, headers={"User-Agent": "GameCam-VO-E7"}), timeout=30) as r:
                body = r.read(2 * 1024 * 1024 + 1)
            if len(body) > 2 * 1024 * 1024:
                raise ValueError("Metadata size cap exceeded")
            (out / name).write_bytes(body)
            return {"file": name, "url": url, "bytes": len(body), "sha256": sha256(out / name), "status": "OK"}
        except Exception as e:
            return {"file": name, "url": url, "status": "FAILED", "error": str(e)}
    with ThreadPoolExecutor(max_workers=6) as pool:
        sources = list(pool.map(fetch, urls.items()))
    probes = [bounded_probe("DROID_W_Metric3D_ViT_Large", "https://huggingface.co/JUGGHM/Metric3D/resolve/main/metric_depth_vit_large_800k.pth", "range"),
              bounded_probe("DROID_W_FiT3D_DINOv2_reg_small", "https://huggingface.co/yuanwenyue/FiT3D/resolve/main/dinov2_reg_small_finetuned.pth", "range")]
    write_json(out / "sources.json", sources)
    write_json(out / "probes.json", probes)
    print(json.dumps({"directory": str(out), "sources": sources, "probes": probes}))


if __name__ == "__main__":
    main()
