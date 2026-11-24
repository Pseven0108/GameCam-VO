"""Read the sealed local Task003/004A records; produce evidence without any model or network calls."""

import csv
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile


OUT = Path(__file__).resolve().parent
EXP = OUT.parent
OBS = EXP / "DROID_W_TASK003_VAL007_OBSERVATION_R1"
PRE = EXP / "DROID_W_TASK004A_RELEASE_READINESS"
CAP = OBS / "remote/capture"
PHASES = ("frontend_local_predecision", "frontend_local_retained")
ORDER = "E3 E4 E7 E0 E8 E6 E1 E2".split()
GIB = 2**30
FLOOR, BUDGET, GATE = (x * GIB for x in (10, 3, 13))


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def identity(path):
    with path.open("rb") as stream:
        return {"bytes": path.stat().st_size, "sha256": hashlib.file_digest(stream, "sha256").hexdigest()}


def write_json(name, data):
    with (OUT / name).open("x", encoding="utf-8", newline="\n") as dest:
        json.dump(data, dest, indent=2, ensure_ascii=False, allow_nan=False)
        dest.write("\n")


def write_csv(name, rows):
    with (OUT / name).open("x", encoding="utf-8-sig", newline="") as dest:
        writer = csv.DictWriter(dest, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def quantiles(values):
    values = sorted(values)
    if not values:
        return {"n": 0}
    assert all(math.isfinite(v) for v in values)
    out = {"n": len(values)}
    for name, p in (("min", 0), ("p05", .05), ("p50", .5), ("p95", .95), ("max", 1)):
        lo, t = divmod((len(values) - 1) * p, 1)
        i = int(lo)
        out[name] = values[i] + t * (values[min(i + 1, len(values) - 1)] - values[i])
    return out


def trace_evidence():
    calls, call_events, distances, decisions, counts = {}, {}, {}, {}, Counter()
    with (CAP / "observer.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            rec = json.loads(line)
            kind = rec["type"]
            counts[kind] += 1
            rid = rec["trigger_rgb_id"]
            if kind == "ba_before" and rec["stage"] in PHASES:
                key = (rec["pid"], rec["ba_id"])
                assert key not in calls
                joint = {r["rgb_id"]: r["slot"] for r in rec["rows"] if r["rgb_id"] in (312, 328)}
                observed_slots = {slot for edge in rec["edge_slots"] for slot in edge}
                both = len(joint) == 2 and all(rec["t0"] <= slot < rec["t1"] and slot in observed_slots for slot in joint.values())
                flags = tuple(int(rec[k]) for k in ("metric_depth_branch_active", "source_uba", "update_u"))
                calls[key] = (rec["stage"], rid, rec["event"], both, flags)
                call_events[key] = [rec["event"]]
            elif kind in ("ba_after_native", "ba_after_clamp") and rec["stage"] in PHASES:
                key = (rec["pid"], rec["ba_id"])
                assert len(call_events[key]) == (1 if kind == "ba_after_native" else 2)
                call_events[key].append(rec["event"])
            elif kind == "frontend_distance":
                assert rid not in distances and rec["rows"][-1]["rgb_id"] == rid
                distances[rid] = (float(rec["score"]), float(rec["threshold"]))
            elif kind == "keyframe_decision":
                assert rid not in decisions
                decisions[rid] = rec["outcome"]

    assert all(len(x) == 3 for x in call_events.values())
    ids = load(CAP / "keyframes.json")["rgb_ids"]
    sealed = load(PRE / "evidence/TASK003_HISTORICAL_REPLAY.json")
    phases = Counter(c[0] for c in calls.values())
    rejected = sum(decisions[rid] == "LOCAL_BA_REJECTED" for _, rid, _, _, _ in calls.values())
    first_id, first = min(((k, c) for k, c in calls.items() if c[3]), key=lambda x: x[1][2])
    for phase in PHASES:
        assert phases[phase] == sealed["trace"]["calls_by_stage"][phase]
    assert rejected == sealed["trace"]["local_returned_rejected"]
    assert len(ids) == sealed["retention"]["keyframe_count"] == len(set(ids))
    assert len(decisions) == 487 and set(decisions) == set(range(1, 488))
    assert set(distances).issubset(decisions)
    assert set(decisions[rid] for rid in distances) == {"RETAINED", "LOCAL_BA_REJECTED"}
    return dict(
        ref="HISTORICAL_TASK003_NOT_E0", raw_trace_events=sum(counts.values()), counters=dict(counts),
        local_calls_by_phase=dict(phases), predecision_pct=100 * phases[PHASES[0]] / sum(phases.values()),
        local_calls_for_rejected_candidates=rejected, decisions=dict(Counter(decisions.values())),
        local_accepted=sum(decisions[rid] == "RETAINED" for rid in distances),
        local_rejected=sum(decisions[rid] == "LOCAL_BA_REJECTED" for rid in distances),
        local_dwu_by_phase={p: dict(Counter("".join(map(str, c[4])) for c in calls.values() if c[0] == p)) for p in PHASES},
        native_distance={"thresholds": sorted({t for _, t in distances.values()}),
                         "all": quantiles([d for d, _ in distances.values()]),
                         "retained": quantiles([d for rid, (d, _) in distances.items() if decisions[rid] == "RETAINED"]),
                         "rejected": quantiles([d for rid, (d, _) in distances.items() if decisions[rid] == "LOCAL_BA_REJECTED"])},
        final_keyframe_rgb_ids=ids, final_keyframes=len(ids),
        final_export_poses=sealed["trace"]["filler_batch_output_frames"],
        first_common_312_328={"phase": first[0], "ba_id": first_id[1], "events": call_events[first_id]})


def storage_capture():
    originals = load(OBS / "FILE_SHA256_MANIFEST.json")["files"]
    old_zip = OBS / "GAMECAM_TASK003_VAL007_OBSERVATION_REVIEW.zip"
    with ZipFile(old_zip) as archive:
        members = {m.filename: m for m in archive.infolist()}
    categories = {"observer.jsonl": "observation", "run.log": "observation", "resource_samples.csv": "observation",
                  "RERUN_RUNTIME.log": "rerun_logs", "native_camera_stream.json": "rerun_logs",
                  "trajectory.npz": "trajectory", "est_poses_full.txt": "trajectory"}
    rows, totals = [], Counter()
    for path in sorted(CAP.rglob("*")):
        if not path.is_file():
            continue
        assert not path.is_symlink()
        name = path.relative_to(OBS).as_posix()
        meta = identity(path)
        sealed = originals[name]
        assert (meta["bytes"], meta["sha256"]) == (sealed["bytes"], sealed["sha256"]), name
        cat = categories.get(path.name, "other")
        totals[cat] += meta["bytes"]
        rows.append({"path": name, **meta, "type": cat, "review_zip_member": name in members,
                     "review_zip_compressed_bytes": members[name].compress_size if name in members else None})

    native_identity = OBS / "evidence/REMOTE_NATIVE_VIDEO_IDENTITY.txt"
    first, second = native_identity.read_text(encoding="utf-8-sig").splitlines()[:2]
    digest, remote_path = first.split(maxsplit=1)
    native_bytes = int(second.removeprefix("bytes="))
    assert len(digest) == 64 and native_bytes > 0
    assert not any(Path(member).name == "video.npz" for member in members)
    samples = table(CAP / "resource_samples.csv")
    series = {k: [int(x[k]) for x in samples if x[k]] for k in
              ("disk_free_bytes", "shm_free_bytes", "cgroup_memory_bytes", "gpu_used_mib", "trace_bytes")}
    return dict(capture_root=str(CAP), capture_files=rows, capture_totals=dict(totals),
                capture_bytes=sum(totals.values()), capture_file_count=len(rows), manifest_matches=len(rows),
                local_rrd_files=sum(Path(r["path"]).suffix.lower() == ".rrd" for r in rows),
                historical_review_zip={"path": str(old_zip), **identity(old_zip), "members": len(members),
                    "payload_uncompressed_bytes": sum(x.file_size for x in members.values()),
                    "capture_members": sum(r["review_zip_member"] for r in rows), "complete_native_attempt": False},
                native_video={"path_recorded": remote_path, "bytes": native_bytes, "sha256_recorded": digest,
                    "status": "HISTORICAL_REMOTE_IDENTITY_ONLY_NO_LOCAL_PAYLOAD_READ", "evidence_file": str(native_identity)},
                resource_samples={"n": len(samples), "first_utc": samples[0]["utc"], "last_utc": samples[-1]["utc"],
                    "ranges": {k: {"first": v[0], "last": v[-1], "min": min(v), "max": max(v)} for k, v in series.items()}},
                historical_full_remote_attempt_directory_bytes=None,
                historical_full_remote_attempt_directory_status="UNVERIFIED_NO_COMPLETE_DU_OR_OUTPUT_INVENTORY")


def phase_rows():
    assets = PRE / "assets"
    matrix = sorted(table(assets / "TASK004_FACTORIAL_MATRIX.csv"), key=lambda x: int(x["screening_slot"]))
    assert [m["arm"] for m in matrix] == ORDER
    assert len({(m["D"], m["W"], m["U"]) for m in matrix}) == 8
    rows = []
    for m in matrix:
        policy = assets / m["policy_file"]
        assert identity(policy)["sha256"] == m["policy_sha256"]
        assert load(policy)["local_dwu"] == [int(m[k]) for k in "DWU"] and m["seed"] == "43"
        for phase in PHASES:
            rows.append(dict(arm=m["arm"], slot=m["screening_slot"], phase=phase, status="NOT_RUN",
                             planned_D=m["D"], planned_W=m["W"], planned_U=m["U"], policy_sha256=m["policy_sha256"],
                             attempt_id=None, completed_ba_calls=None, actual_dwu_counts=None, accepted_candidates=None,
                             rejected_candidates=None, native_distance_n=None, native_distance_p05=None,
                             native_distance_p50=None, native_distance_p95=None, final_keyframe_ids=None,
                             e0_shared_keyframe_count=None, rgb312_retained=None, rgb328_retained=None))
    return rows


def simulate(capture, receiver_free):
    starts = {
        "TASK003_EARLIER_PREFLIGHT": int(load(EXP / "DROID_W_TASK003_GPU_PREFLIGHT_RECHECK_20261122T183753Z/REMOTE_GPU_RESOURCES.json")["filesystems"]["/root/rivermind-data"]["bytes_available"]),
        "TASK003_FINAL_PREFLIGHT": int(load(OBS / "evidence/TASK003_FINAL_PREFLIGHT.json")["disk_free_bytes"]),
    }
    known = capture["capture_bytes"] + capture["native_video"]["bytes"]
    count = capture["capture_file_count"] + 1
    known_zip = known + known // 100 + 4096 * count + 2**20  # Reviewed scheduler's archive allowance.
    workloads = {"KNOWN_OUTPUT_PROXY": (known, known_zip), "FULL_3GIB_REMOTE_BUDGET": (BUDGET // 2, BUDGET // 2)}
    rows = []
    for start_id, initial in starts.items():
        for scenario, (raw, zip_size) in workloads.items():
            for placement in ("REMOTE_ZIP_INDEPENDENT_LOCAL_COPY", "BOTH_ZIPS_ON_SOURCE_FILESYSTEM"):
                same = placement == "BOTH_ZIPS_ON_SOURCE_FILESYSTEM"
                remote_peak = raw + zip_size * (2 if same else 1)
                receiver_peak = 0 if same else zip_size
                source_need = max(GATE, FLOOR + remote_peak) + (len(ORDER) - 1) * remote_peak
                receiver_need = 0 if same else (len(ORDER) - 1) * receiver_peak + max(BUDGET, receiver_peak)
                source_free, recv_free = initial, receiver_free
                stop = None
                for slot, arm in enumerate(ORDER, start=1):
                    if stop is not None:
                        state = "NOT_REACHED_AFTER_BLOCK"
                    elif source_free < GATE:
                        state = "BLOCKED_SOURCE_ADMISSION"
                    elif remote_peak > BUDGET:
                        state = "BLOCKED_PER_ARM_PEAK_BUDGET"
                    elif not same and recv_free < max(BUDGET, zip_size):
                        state = "BLOCKED_RECEIVER_ADMISSION"
                    elif source_free - remote_peak < FLOOR:
                        state = "BLOCKED_RESERVE_FLOOR"
                    else:
                        state = "SIMULATED_FITS"
                    if state.startswith("BLOCKED"):
                        stop = arm
                    # Projection columns are scenario arithmetic; state identifies the first actual simulated stop.
                    rows.append(dict(initial_ref=start_id, scenario=scenario, placement=placement, slot=slot, arm=arm,
                                     status=state, first_blocked_arm=stop, source_initial_free_bytes=initial,
                                     source_before_bytes=source_free, source_gate_bytes=GATE,
                                     source_peak_new_bytes=remote_peak, source_run_only_bytes=raw,
                                     source_free_after_run_if_executed_bytes=source_free-raw,
                                     archive_single_copy_bytes=zip_size,
                                     source_free_after_same_disk_zip_if_executed_bytes=source_free-raw-zip_size,
                                     source_free_at_copy_peak_if_executed_bytes=source_free-remote_peak,
                                     independent_receiver_before_bytes=None if same else recv_free,
                                     independent_receiver_copy_peak_new_bytes=None if same else receiver_peak,
                                     independent_receiver_free_at_copy_peak_if_executed_bytes=None if same else recv_free-receiver_peak,
                                     all_eight_source_start_min_bytes=source_need if remote_peak <= BUDGET else None,
                                     all_eight_receiver_start_min_bytes=None if same else receiver_need))
                    if state == "SIMULATED_FITS":
                        source_free -= remote_peak
                        recv_free -= receiver_peak
    return rows, dict(starts=starts, known_output_proxy={"raw_bytes": known, "zip_allowance_bytes": known_zip,
                    "file_count": count}, source_gate_bytes=GATE, floor_bytes=FLOOR, budget_bytes=BUDGET,
                    full_budget_example={"raw_bytes": BUDGET//2, "zip_bytes": BUDGET//2},
                    forecast="SIMULATION_ONLY_NO_CURRENT_REMOTE_DISK_MEASUREMENT")


def main():
    receiver = json.load(sys.stdin)
    assert receiver["volume"]["FileSystem"] == "NTFS" and len(receiver["reparse_components"]) == 0
    prior_archive = load(PRE / "TASK004A_ZIP_VALIDATION.json")
    assert identity(Path(prior_archive["zip"])) == {"bytes": prior_archive["bytes"], "sha256": prior_archive["zip_sha256"]}
    prior_manifest = load(PRE / "FILE_SHA256_MANIFEST.json")["files"]
    prior_rel = ["tools/scheduler.py", "tools/trace_audit.py", "assets/candidates/task004_controls.py",
                 "assets/candidates/task004_run_segment.py", "assets/candidates/preview/src/frontend.py",
                 "_local_probe/probe_05/browser_after.png"]
    protected = {p: identity(PRE / p) for p in prior_rel}
    assert all(protected[p] == prior_manifest[p] for p in prior_rel)
    capture = storage_capture()
    trace = trace_evidence()
    phase = phase_rows()
    sims, simulation_inputs = simulate(capture, int(receiver["volume"]["SizeRemaining"]))
    write_csv("TASK004A_EIGHT_ARM_STORAGE_SIMULATION.csv", sims)
    write_csv("TASK004A_ARM_PHASE_STATISTICS.csv", phase)
    write_json("TASK004A_LOCAL_EVIDENCE.json", dict(captured_utc=datetime.now(timezone.utc).isoformat(),
        previous_release=prior_archive, unchanged_samples=protected, historical_task003_capture=capture,
        historical_task003_trace=trace, simulation_inputs=simulation_inputs, local_receiver=receiver,
        arm_rows=len(phase), simulation_rows=len(sims), formal_runs=0, remote_connections=0))
    print(json.dumps({"capture_bytes": capture["capture_bytes"], "capture_file_count": capture["capture_file_count"],
        "capture_totals": capture["capture_totals"], "review_zip": capture["historical_review_zip"],
        "resources": capture["resource_samples"], "history": {k: v for k, v in trace.items() if k != "final_keyframe_rgb_ids"},
        "receiver": receiver, "simulation_inputs": simulation_inputs,
        "first_blocks": [{k: r[k] for k in ("initial_ref", "scenario", "placement", "arm", "source_before_bytes", "status",
                       "source_peak_new_bytes", "all_eight_source_start_min_bytes", "all_eight_receiver_start_min_bytes")}
                         for r in sims if r["status"].startswith("BLOCKED")]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
