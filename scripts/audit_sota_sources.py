"""E7 read-only host/repository/asset probes. Does not install or fetch checkpoints."""
from __future__ import annotations
import _bootstrap
import concurrent.futures
import hashlib
import importlib.util
import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import psutil
from gamecam_vo.common import PROJECT, make_run_dir, run_metadata, sha256, write_json

REPOSITORIES = {
    "DROID_W": ("droid_w", "MoyangLi00/DROID-W", "c3414af6047d06bafc1a6645d09f23247f3b2cdc"),
    "BA_TRACK": ("ba_track", "wrchen530/batrack", "456e094ee3ca7fbd9884ba18e68e7c0717d49a67"),
    "PI3MOS": ("pi3mos", "PRBonn/Pi3MOS-SLAM", "5e709d27324a935e364e01efc56f3128ac00bf24"),
}


def command(args, timeout=30):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout)
        def decode(b):
            return b.decode("utf-16-le" if b"\0" in b else "utf-8", errors="replace").strip()
        return {"exit_code": p.returncode, "stdout": decode(p.stdout), "stderr": decode(p.stderr)}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"error": str(e)}


def bounded_probe(label, url, mode="head"):
    result = {"label": label, "requested_url": url, "mode": mode, "full_asset_downloaded": False}
    headers = {"User-Agent": "GameCam-VO E7 metadata audit", "Accept-Encoding": "identity"}
    if mode == "range":
        headers["Range"] = "bytes=0-7"
    try:
        request = Request(url, headers=headers, method="HEAD" if mode == "head" else "GET")
        with urlopen(request, timeout=25) as response:
            result.update(http_status=response.status, final_host=response.url.split("/")[2],
                          content_type=response.headers.get("Content-Type"), content_length=response.headers.get("Content-Length"),
                          content_range=response.headers.get("Content-Range"),
                          content_disposition=response.headers.get("Content-Disposition"))
            limit = 0 if mode == "head" else (65536 if mode == "page" else 8)
            body = response.read(limit) if limit else b""
            result["application_body_bytes_read"] = len(body)
            if mode == "page":
                text = body.decode("utf-8", errors="replace")
                title = re.search(r"<title>(.*?)</title>", text, re.S)
                result["title"] = title.group(1) if title else None
                result["display_sizes"] = sorted(set(re.findall(r"\b\d+(?:\.\d+)?\s*(?:GB|MB|KB|bytes)\b", text, re.I)))[:15]
                result["body_truncated_at_limit"] = len(body) == limit
            elif mode == "range":
                result["prefix_hex"] = body.hex()
                result["binary_prefix_verified"] = bool(body and not body.lstrip().startswith((b"<", b"{", b"Error")) and
                                                       "text/html" not in (result["content_type"] or ""))
            if response.status == 206 and result.get("content_range"):
                match = re.search(r"/(\d+)$", result["content_range"])
                if match:
                    result["published_total_bytes"] = int(match.group(1))
            elif response.status == 200 and result.get("content_length") and "text/html" not in (result.get("content_type") or ""):
                result["published_total_bytes"] = int(result["content_length"])
    except HTTPError as e:
        result.update(http_status=e.code, error=str(e), application_body_bytes_read=0)
    except Exception as e:
        result.update(error=f"{type(e).__name__}: {e}")
    return result


def main():
    out = make_run_dir(PROJECT / "results/E7_SOTA_AUDIT", "source_and_host_audit")
    memory = psutil.virtual_memory()
    environment = {**run_metadata(), "client_date": "2026-10-31", "client_timezone": "Asia/Shanghai",
       "python": sys.version, "python_executable": sys.executable, "platform": platform.platform(),
       "ram_bytes": memory.total, "available_ram_bytes": memory.available,
       "physical_cores": psutil.cpu_count(logical=False), "logical_cores": psutil.cpu_count(),
       "project_torch_installed": importlib.util.find_spec("torch") is not None,
       "gpu": command(["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version,compute_cap", "--format=csv"]),
       "windows_nvcc": command(["nvcc", "--version"]), "conda_environments": command(["conda", "env", "list", "--json"]),
       "wsl_distributions": command(["wsl", "-l", "-v"]),
       "wsl_runtime": command(["wsl", "-d", "Ubuntu", "--exec", "/bin/bash", "--noprofile", "--norc", "-c",
          "cat /etc/os-release; uname -r; free -b; df -B1 / /mnt/d; command -v conda || true; command -v nvcc || true; python3 --version; /usr/lib/wsl/lib/nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version,compute_cap --format=csv"]),
       "disk": {d: {"free_bytes": shutil.disk_usage(d).free, "total_bytes": shutil.disk_usage(d).total} for d in ("C:/", "D:/")}}
    write_json(out / "environment.json", environment)
    repos = {}
    for label, (folder, slug, expected) in REPOSITORIES.items():
        root = PROJECT / "baselines" / folder / "upstream"
        revision = command(["git", "-C", str(root), "rev-parse", "HEAD"])["stdout"]
        if revision != expected:
            raise ValueError(f"Unexpected source revision for {label}")
        tree = subprocess.check_output(["git", "-C", str(root), "ls-tree", "-rlz", "HEAD"])
        files = []
        for line in tree.split(b"\0"):
            if not line:
                continue
            left, name = line.split(b"\t", 1)
            fields = left.decode().split()
            files.append({"path": name.decode(), "mode": fields[0], "type": fields[1], "git_oid": fields[2],
                          "bytes": int(fields[3]) if fields[3] != "-" else None})
        local = [p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts and p.suffix in (".py", ".yaml", ".yml", ".sh", ".cu", ".cpp", ".h", ".md", ".txt")]
        repos[label] = {"repository": "https://github.com/" + slug, "revision": revision,
                        "source_checkout": str(root), "checkout_mode": "shallow sparse source-only; media and model binaries not checked out",
                        "tracked_files": files, "tracked_blob_total_bytes": sum(v["bytes"] or 0 for v in files),
                        "submodule_status": command(["git", "-C", str(root), "submodule", "status"]),
                        "readme_sha256": sha256(root / "README.md"), "top_level_license_present": (root / "LICENSE").is_file(),
                        "inspected_source_sha256": {p.relative_to(root).as_posix(): sha256(p) for p in local}}
        (out / label).mkdir()
        for filename in ("README.md", "LICENSE", "environment.yml", "requirements.txt", "setup.py", ".gitmodules"):
            if (root / filename).is_file():
                shutil.copy2(root / filename, out / label / filename)
    write_json(out / "repositories.json", repos)
    drive_ids = {"DROID_W_droid": "1PpqVt1H4maBa_GbPJp4NwxRsd9jk-elh", "BA_TRACK_tracker": "1wWK_ur0Pr4jivqDUdyRUFzHPaF-f1clC",
                 "BA_TRACK_DAVIS_demo": "1hlHyxqW0AaPrv6NwJya0P2UJpcVNYbBU", "PI3MOS_dpvo": "1lyDijcDAsqMXBYgQkPnZ_1tKJfYfSXnU",
                 "PI3MOS_core": "145bC76pMHikhdTGkqDK0t9Ta0R7tw51v"}
    work = []
    for name, identifier in drive_ids.items():
        work.extend([(name + "_public_page", f"https://drive.google.com/file/d/{identifier}/view", "page"),
                     (name + "_download_probe", f"https://drive.usercontent.google.com/download?id={identifier}&export=download&confirm=t", "range")])
    work += [("BA_TRACK_DepthAnythingV2", "https://huggingface.co/depth-anything/Depth-Anything-V2-Large/resolve/main/depth_anything_v2_vitl.pth", "range"),
             ("PI3MOS_DPVO_legacy_archive", "https://www.dropbox.com/s/nap0u8zslspdwm4/models.zip?dl=1", "head"),
             ("DROID_W_official_Bonn_balloon", "https://www.ipb.uni-bonn.de/html/projects/rgbd_dynamic2019/rgbd_bonn_balloon.zip", "head")]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        probes = list(pool.map(lambda args: bounded_probe(*args), work))
    write_json(out / "asset_probes.json", probes)
    write_json(PROJECT / "reports/SOTA/latest_E7.json", {"directory": str(out), "status": "EVIDENCE_COLLECTED_REQUIRES_REVIEW"})
    print(json.dumps({"directory": str(out), "repositories": {k: v["revision"] for k, v in repos.items()},
                      "probes": [{k: row.get(k) for k in ("label", "http_status", "published_total_bytes", "binary_prefix_verified", "title", "error")} for row in probes]}))


if __name__ == "__main__":
    main()
