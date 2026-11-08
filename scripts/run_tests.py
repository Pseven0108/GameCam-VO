from __future__ import annotations
import _bootstrap
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone

from gamecam_vo.common import PROJECT, write_json


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    parent = (PROJECT / "tests/_artifacts").resolve()
    parent.mkdir(parents=True, exist_ok=True)
    base = (parent / run_id).resolve()
    if not base.is_relative_to(parent) or base.exists():
        raise ValueError("Test directory must be a NEW directory strictly inside project tests/_artifacts")
    # pytest may clear --basetemp, so pass only a verified, unique, nonexistent path.
    logfile = PROJECT / "logs" / f"unit_tests_{run_id}.log"
    xmlfile = PROJECT / "logs" / f"unit_tests_{run_id}.xml"
    command = [sys.executable, "-m", "pytest", "-q", "--tb=short",
               f"--basetemp={base}", f"--junitxml={xmlfile}"]
    value = subprocess.run(command, cwd=PROJECT, capture_output=True, text=True, errors="replace")
    logfile.write_text(value.stdout + value.stderr, encoding="utf-8")
    print(value.stdout, end="")
    if value.stderr:
        print(value.stderr, file=sys.stderr, end="")
    summary = {"status": "PASS" if value.returncode == 0 else "FAIL", "exit_code": value.returncode,
               "log": str(logfile), "junit_xml": str(xmlfile), "synthetic_unit_test_directory": str(base),
               "note": "Synthetic fixtures only; these are not WildWorld experimental results."}
    write_json(PROJECT / "logs/latest_tests.json", summary)
    print(json.dumps(summary, ensure_ascii=False))
    return value.returncode


if __name__ == "__main__":
    raise SystemExit(main())
