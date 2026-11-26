"""Bounded HTTP-Range TAR prefix extraction, exact9 planned pairs at most.

No model, GPU, full archive, auth token, retries, substituted frame or re-encode.
Full LFS/gzip CRC cannot be certified from a prefix; PNG CRC is checked instead.
"""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import struct
import tarfile
import time
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REV = "4e34897a2fcf8e1cc44b1ae8d2bbd0188c8f2841"
LIMIT = 32 * 1024**2
TOTAL_LIMIT = 256 * 1024**2
STATE = {"compressed_bytes_read": 0, "streams": [], "files": [], "UID_checks": [], "model_forwards": 0,
         "GPU_used": False, "full_archive_SHA_verified": False, "full_gzip_CRC_verified": False, "auto_retry": False}


def dump(name, obj):
    p = ROOT / name; p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8") as f: json.dump(obj, f, indent=2, ensure_ascii=False, allow_nan=False); f.write("\n")


class BudgetReader:
    def __init__(self, response, record): self.response = response; self.record = record
    def read(self, n=-1):
        if n < 0: raise RuntimeError("Unbounded network read forbidden")
        room = min(LIMIT - self.record["compressed_bytes_read"], TOTAL_LIMIT - STATE["compressed_bytes_read"])
        if room <= 0: raise RuntimeError("DOWNLOAD_BUDGET_STOP")
        b = self.response.read(min(n, room))
        STATE["compressed_bytes_read"] += len(b); self.record["compressed_bytes_read"] += len(b)
        return b


def verify_png(raw, depth):
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")
    # Verify every stored PNG chunk CRC, not the surrounding truncated gzip CRC.
    import zlib
    at = 8; chunks = 0
    while at < len(raw):
        length = struct.unpack_from(">I", raw, at)[0]
        end = at + 12 + length
        if end > len(raw): raise ValueError("Truncated PNG chunk")
        tag = raw[at+4:at+8]; data = raw[at+8:at+8+length]
        expected = struct.unpack_from(">I", raw, at+8+length)[0]
        if zlib.crc32(tag + data) & 0xffffffff != expected: raise ValueError("PNG CRC mismatch")
        chunks += 1; at = end
        if tag == b"IEND": break
    if at != len(raw): raise ValueError("Unexpected data after PNG IEND")
    with Image.open(io.BytesIO(raw)) as im: im.verify()
    with Image.open(io.BytesIO(raw)) as im:
        im.load(); arr = np.asarray(im)
        if depth and (arr.ndim != 2 or arr.dtype != np.uint16): raise ValueError("Depth is not uint16 grayscale")
        if not depth and (arr.ndim != 3 or arr.shape[2] not in [3, 4]): raise ValueError("RGB layout not admitted")
        return {"width": im.width, "height": im.height, "mode": im.mode, "dtype": str(arr.dtype), "PNG_chunks_verified": chunks}


def fetch(candidate, archive, modality):
    uid = candidate["uid"]
    url = "https://huggingface.co/datasets/InternRobotics/OmniWorld/resolve/" + REV + "/" + archive["path"]
    record = {"uid": uid, "source_path": archive["path"], "revision": REV,
              "official_archive_bytes": int(archive["bytes"]), "official_LFS_sha256": archive["lfs_sha256"],
              "Range_requested": f"bytes=0-{LIMIT-1}", "compressed_bytes_read": 0, "members_visited": 0,
              "expected_frames": candidate["frames"], "retrieved_frames": [], "HTTP_identity_only_not_full_SHA": True}
    STATE["streams"].append(record)
    request = urllib.request.Request(url, headers={"User-Agent": "GameCam-VO-TASK007C-Bounded-GT-Audit",
                                                  "Range": f"bytes=0-{LIMIT-1}", "Accept-Encoding": "identity"})
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=45) as response:
        record.update(HTTP_status=response.status, Content_Range=response.headers.get("Content-Range"),
                      ETag=response.headers.get("ETag"), final_host=urllib.parse.urlparse(response.url).hostname)
        if response.status != 206: raise RuntimeError("SERVER_IGNORED_RANGE_STOP_BEFORE_BODY")
        match = re.fullmatch(r"bytes 0-(\d+)/(\d+)", record["Content_Range"] or "")
        if match is None or int(match[2]) != int(archive["bytes"]) or int(match[1]) + 1 > LIMIT:
            raise RuntimeError("RANGE_IDENTITY_MISMATCH")
        reader = BudgetReader(response, record)
        wanted = {f"{i:06d}.png": i for i in candidate["frames"]}
        with tarfile.open(fileobj=reader, mode="r|gz") as z:
            for member in z:
                record["members_visited"] += 1
                if time.perf_counter() - start > 120: raise RuntimeError("STREAM_TIME_LIMIT")
                leaf = PurePosixPath(member.name).name
                if leaf not in wanted: continue
                parts = PurePosixPath(member.name).parts
                expected_dir = "depth" if modality == "depth" else "color"
                if expected_dir not in parts or not member.isfile(): raise RuntimeError("Unexpected approved member location")
                if member.size > 16 * 1024**2: raise RuntimeError("PNG member exceeds bounded-size contract")
                raw = z.extractfile(member).read()
                if len(raw) != member.size: raise RuntimeError("Incomplete TAR member")
                proof = verify_png(raw, modality == "depth")
                target = ROOT / "raw_inputs" / uid / expected_dir / leaf
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as f: f.write(raw)
                frame = wanted.pop(leaf)
                record["retrieved_frames"].append(frame)
                STATE["files"].append({"uid": uid, "frame": frame, "modality": modality, "member": member.name,
                    "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "path": str(target), **proof})
                if not wanted: break
        if wanted: raise RuntimeError("MISSING_APPROVED_MEMBER_NO_SUBSTITUTION")
    record["elapsed_seconds"] = time.perf_counter() - start
    record["prefix_transfer_complete_for_requested_members"] = True


def check_uid(candidate):
    uid = candidate["uid"]; camera = json.loads((ROOT / "raw_inputs" / uid / "camera/split_0.json").read_text())
    checks = []
    for f in candidate["frames"]:
        rp = ROOT / "raw_inputs" / uid / "color" / f"{f:06d}.png"
        dp = ROOT / "raw_inputs" / uid / "depth" / f"{f:06d}.png"
        with Image.open(rp) as im: im.load(); rgb_shape = (im.height, im.width)
        with Image.open(dp) as im: im.load(); raw = np.asarray(im)
        if raw.shape != rgb_shape or raw.shape != (720, 1280): raise RuntimeError("RGB_DEPTH_RESOLUTION_ALIGNMENT_STOP")
        j = candidate["frames"].index(f)
        fx = float(camera["focals"][j]); cx = float(camera["cx"]) + .5; cy = float(camera["cy"]) + .5
        if not all(np.isfinite([fx, cx, cy])) or fx <= 0: raise RuntimeError("CAMERA_INTRINSICS_STOP")
        v = raw.astype(np.float32) / np.float32(65535.)
        mask = ~(v < np.float32(.0015)) & ~(v > np.float32(65500. / 65535.))
        decoded = v / (np.float32(1000.) - v * np.float32(999.)) / np.float32(.004)
        decoded[~mask] = -1
        decoded[mask] *= np.float32(candidate["metric_scale"])
        if not mask.any() or not np.isfinite(decoded[mask]).all() or (decoded[mask] <= 0).any(): raise RuntimeError("DEPTH_DECODE_OR_MASK_STOP")
        checks.append({"uid": uid, "frame": f, "RGB_depth_shape": list(raw.shape), "uint16": True,
            "source_metric_scale": candidate["metric_scale"], "source_defined_unit": "Declared meters after documented scaling",
            "fx_fy": fx, "cx_plus_half": cx, "cy_plus_half": cy, "GT_valid_pixels": int(mask.sum()),
            "GT_valid_fraction": float(mask.mean()), "raw_min": int(raw.min()), "raw_max": int(raw.max()),
            "metric_depth_quantiles": np.percentile(decoded[mask], [0, 1, 50, 99, 100]).astype(float).tolist(),
            "mask_exact_source_rule": True, "percentile_far_filter_used": False,
            "independent_physical_metric_accuracy": "UNVERIFIED", "pixelwise_RGB_alignment": "PENDING_VISUAL_AND_EDGE_AUDIT"})
    STATE["UID_checks"].extend(checks)


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1"
    candidates = json.loads((ROOT / "evidence/CANDIDATE_INTAKE.json").read_text("utf-8"))["candidates"]
    try:
        for c in candidates:
            # Complete one UID's basic data checks before acquiring the next.
            for modality, suffix in [("depth", "_depth_0000.tar.gz"), ("rgb", "_rgb_0000.tar.gz")]:
                fetch(c, next(a for a in c["needed_archives"] if a["path"].endswith(suffix)), modality)
            check_uid(c)
            print("Basic UID decode complete:", c["uid"], flush=True)
        STATE["status"] = "EXACT_MINIMAL_PAIRS_ACQUIRED_BASIC_SOURCE_CONTRACT_ONLY"
    except Exception as e:
        STATE["status"] = "STOPPED_NO_RETRY_NO_FURTHER_ACQUISITION"
        STATE["failure_type"] = type(e).__name__
        # Do not log URLs from HTTP errors: redirects can carry bearer query data.
        STATE["failure_reason"] = str(e) if not isinstance(e, (urllib.error.HTTPError, urllib.error.URLError)) else "PUBLIC_RANGE_ACCESS_FAILED"
        dump("evidence/ACQUISITION_RECEIPT.json", STATE)
        raise SystemExit("Stopped acquisition; inspect sanitized receipt")
    dump("evidence/ACQUISITION_RECEIPT.json", STATE)
    print(json.dumps({"status": STATE["status"], "compressed_bytes_read": STATE["compressed_bytes_read"], "PNG_files": len(STATE["files"])}, indent=2))


if __name__ == "__main__": main()
