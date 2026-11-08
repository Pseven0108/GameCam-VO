"""Bounded, read-only checks of public asset hosts using current and direct routing."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import time
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener


def check(item):
    host, route = item
    started = time.monotonic()
    opener = build_opener() if route == "current_environment_proxy" else build_opener(ProxyHandler({}))
    try:
        with opener.open(Request("https://" + host + "/robots.txt", headers={"User-Agent": "GameCam-VO-connectivity-probe"}), timeout=12) as response:
            count = len(response.read(1024))
            result = {"http_status": response.status, "bytes_read_capped_1024": count}
    except HTTPError as exc:
        result = {"http_status": exc.code, "network_error": None}
    except Exception as exc:
        result = {"http_status": None, "network_error": f"{type(exc).__name__}: {exc}"}
    return {"host": host, "route": route, "elapsed_seconds": time.monotonic()-started, **result}


def main():
    hosts = ["conda.anaconda.org", "pypi.org", "huggingface.co", "pypi.tuna.tsinghua.edu.cn"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(check, [(host, route) for host in hosts for route in ("current_environment_proxy", "direct_no_proxy")]))
    print(json.dumps({"checks": records, "system_proxy_configuration_modified": False, "ssl_verification_disabled": False}, indent=2), flush=True)


if __name__ == "__main__":
    main()
