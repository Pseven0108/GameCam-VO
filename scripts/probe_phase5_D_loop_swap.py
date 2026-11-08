"""Probe only a fresh owned D-drive file as a temporary Linux loop swap area."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(args):
    p = subprocess.run(args, capture_output=True, text=True)
    return {"command": args, "exit_code": p.returncode, "stdout": p.stdout, "stderr": p.stderr}


def swaps():
    return [line.split() for line in Path("/proc/swaps").read_text().splitlines()[1:]]


def verify_owned(loop, file, size):
    if not re.fullmatch(r"/dev/loop\d+", loop) or not stat.S_ISBLK(os.stat(loop).st_mode):
        raise ValueError("Only an owned loop block device may be touched")
    info = run(["losetup", "--json", "--list", "--output", "NAME,BACK-FILE,OFFSET,SIZELIMIT,RO", loop])
    rows = json.loads(info["stdout"])["loopdevices"]
    if (len(rows) != 1 or rows[0]["name"] != loop or Path(rows[0]["back-file"]).resolve() != file.resolve()
        or int(rows[0]["offset"]) != 0 or int(rows[0]["sizelimit"]) != 0 or rows[0]["ro"]):
        raise ValueError("Loop ownership/offset/writeability check failed")
    actual = run(["blockdev", "--getsize64", loop])
    if actual["exit_code"] or int(actual["stdout"]) != size:
        raise ValueError("Owned raw-file and block-device size disagree")
    if any(line.split()[0] == loop for line in Path("/proc/mounts").read_text().splitlines()):
        raise ValueError("Never format a mounted loop")
    return rows[0]


def main():
    if os.name != "posix" or os.geteuid() != 0 or str(ROOT) != "/mnt/d/aaa/GameCam-VO":
        raise RuntimeError("Require root in the existing WSL and exact owned project")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    folder = ROOT / "data/phase5_runtime" / (stamp+"_owned_loop_swap_probe")
    folder.mkdir(parents=True, exist_ok=False)
    if folder.resolve().parent != (ROOT / "data/phase5_runtime").resolve():
        raise ValueError("Owned probe path escaped workspace")
    size = 64*1024**2
    if shutil.disk_usage(folder).free < size+5*1024**3:
        raise RuntimeError("Insufficient D-drive headroom")
    file = folder / "owned_64MiB.raw"
    with file.open("xb") as stream:
        block = bytes(1024**2)
        for _ in range(64):
            stream.write(block)
        stream.flush(); os.fsync(stream.fileno())
    log = ROOT / "logs/PHASE5" / (stamp+"_D_loop_swap_probe")
    log.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, log / "probe_phase5_D_loop_swap.py.executed_source")
    report = {"status": "PROBE_RUNNING", "created_at_utc": datetime.now(timezone.utc).isoformat(), "file": str(file), "bytes": size,
        "prior_swaps": swaps(), "commands": [], "native_model_or_environment_changed": False, "WSL_restarted": False}
    attached = run(["losetup", "--find", "--show", "--nooverlap", str(file)])
    report["commands"].append(attached)
    if attached["exit_code"]:
        report["status"] = "OWNED_LOOP_ATTACH_UNAVAILABLE"
    else:
        loop = attached["stdout"].strip()
        report["loop"] = loop
        report["verified_owned_mapping"] = verify_owned(loop, file, size)
        # Read/write only this freshly created raw-file block device, before
        # making it swap. Never access an existing disk/partition/device.
        payload = b"GameCam-VO-owned-D-loop-IO-probe"*256
        with open(loop, "r+b", buffering=0) as stream:
            stream.seek(1024**2); stream.write(payload); stream.flush(); os.fsync(stream.fileno())
            stream.seek(1024**2)
            if stream.read(len(payload)) != payload:
                raise ValueError("Owned loop read/write roundtrip failed")
        created = run(["mkswap", "--label", "GameCamP5Probe", loop])
        report["commands"].append(created)
        if created["exit_code"]:
            report["status"] = "OWNED_LOOP_SWAP_HEADER_UNAVAILABLE"
        else:
            activated = run(["swapon", "--priority", "-4", loop])
            report["commands"].append(activated)
            report["status"] = "OWNED_D_LOOP_SWAP_ACTIVATION_PASS" if activated["exit_code"] == 0 else "OWNED_D_LOOP_SWAP_ACTIVATION_UNAVAILABLE"
            report["swaps_after_activation"] = swaps()
        active = next((r for r in swaps() if r[0] == loop), None)
        if active:
            if int(active[3]) != 0:
                raise RuntimeError("Owned probe acquired swap pages; leave it active rather than detach it")
            verify_owned(loop, file, size)
            off = run(["swapoff", loop]); report["commands"].append(off)
            if off["exit_code"]:
                raise RuntimeError("Owned probe swapoff failed; never detach an active swap device")
        if any(r[0] == loop for r in swaps()):
            raise RuntimeError("Owned probe remains active; refuse detachment")
        verify_owned(loop, file, size)
        detached = run(["losetup", "--detach", loop])
        report["commands"].append(detached)
        report["owned_probe_detached"] = detached["exit_code"] == 0
    report["prior_swap_entries_preserved"] = all(any(r[0] == old[0] for r in swaps()) for old in report["prior_swaps"])
    (log / "probe.json").write_text(json.dumps(report, indent=2)+"\n")
    (ROOT / "reports/PHASE5/D_loop_swap_probe.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
