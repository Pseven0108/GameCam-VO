"""Bounded metadata-only follow-up for VIPER-related non-ZIP containers."""
import hashlib
import json
from pathlib import Path
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "local_audit/LOCAL_SEARCH_SUMMARY.json").read_text("utf-8"))
rows = []
limit = 256 * 1024**2
for entry in data["unparsed_containers"]:
    p = Path(entry["archive"])
    if not any(s in str(p).lower() for s in ["viper", "dense"]):
        continue
    r = {"archive": str(p), "bytes": p.stat().st_size, "status": "UNVERIFIED", "headers_read": 0,
         "depth_like_member_names": [], "payload_extracted": False,
         "compressed_scan_limit_bytes": limit, "GT_admitted": False}
    if p.name.lower().endswith((".tar", ".tar.gz", ".tgz")):
        compressed = not p.name.lower().endswith(".tar")
        start = time.perf_counter(); digest = hashlib.sha256()
        try:
            with tarfile.open(p, "r|gz" if compressed else "r:") as t:
                for m in t:
                    r["headers_read"] += 1
                    digest.update(f"{m.name}\t{m.size}\t{m.type!r}\n".encode("utf-8"))
                    if any(s in m.name.lower() for s in ["depth", "dispar", "ground_truth", "groundtruth"]) or m.name.lower().endswith((".exr", ".pfm")):
                        r["depth_like_member_names"].append({"member": m.name, "bytes": m.size,
                            "status": "HEADER_ONLY_NOT_GT_PROVENANCE"})
                    if compressed and (m.offset_data + m.size > limit or time.perf_counter() - start > 10):
                        r["status"] = "BOUNDED_PREFIX_ONLY_REMAINDER_UNVERIFIED"; break
                else:
                    r["status"] = "ALL_TAR_HEADERS_READ"
            r["header_identity_sha256"] = digest.hexdigest()
        except (tarfile.TarError, OSError) as e:
            r["status"] = "UNPARSED_" + type(e).__name__
    rows.append(r)
result = {"containers": rows, "containers_attempted": len(rows),
          "complete_header_inspections": sum(r["status"] == "ALL_TAR_HEADERS_READ" for r in rows),
          "incomplete_or_unverified": [r["archive"] for r in rows if r["status"] != "ALL_TAR_HEADERS_READ"],
          "GT_admitted": 0, "scope": "VIPER/dense context paths selected from previously disclosed non-ZIP inventory; all other non-ZIPs remain unverified"}
with (ROOT / "local_audit/VIPER_TAR_FOLLOWUP.json").open("x", encoding="utf-8") as f:
    json.dump(result, f, indent=2); f.write("\n")
print(json.dumps({k: v for k, v in result.items() if k != "containers"}, indent=2))
