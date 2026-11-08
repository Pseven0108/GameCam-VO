"""One bounded availability check of the same official public weight URL."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time


ROOT = Path("/mnt/d/aaa/GameCam-VO")
URL = "https://drive.usercontent.google.com/download?id=145bC76pMHikhdTGkqDK0t9Ta0R7tw51v&export=download&confirm=t"


def main():
    out = ROOT / "logs/SOTA_setup" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "_pi3mos_availability_check")
    out.mkdir(exist_ok=False)
    start, end, total = 892229187, 892294722, 4100235800
    command = ["curl", "--fail", "--location", "--connect-timeout", "10", "--max-time", "30",
               "--range", f"{start}-{end}", "--max-filesize", str(end-start+1), URL,
               "--output", str(out / "response.body"), "--dump-header", str(out / "response.headers")]
    with (out / "request.log").open("w") as log:
        code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT).returncode
    headers = (out / "response.headers").read_text() if (out / "response.headers").exists() else ""
    body = (out / "response.body").read_bytes() if (out / "response.body").exists() else b""
    ranges = re.findall(r"(?im)^content-range:\s*bytes\s+(\d+)-(\d+)/(\d+)\s*$", headers)
    available = code == 0 and len(body) == end-start+1 and bool(ranges) and tuple(map(int, ranges[-1])) == (start, end, total)
    quota = b"quota" in body.lower() or b"too many users" in body.lower()
    record = {"status": "OFFICIAL_RANGE_AVAILABLE" if available else ("OFFICIAL_PUBLIC_DOWNLOAD_QUOTA_STILL_BLOCKED" if quota else "OFFICIAL_DOWNLOAD_NOT_VERIFIED_AVAILABLE"),
              "checked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "directory": str(out), "source": URL,
              "command": command, "exit_code": code, "body_bytes": len(body), "body_sha256": hashlib.sha256(body).hexdigest(),
              "verified_model_bytes": len(body) if available else 0, "quota_text_detected": quota,
              "automatic_retries": False, "different_account_or_quota_bypass": False,
              "original_verified_partial_downloads_unchanged": True}
    (out / "status.json").write_text(json.dumps(record, indent=2)+"\n")
    (ROOT / "reports/SOTA/pi3mos_download_availability.json").write_text(json.dumps(record, indent=2)+"\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
