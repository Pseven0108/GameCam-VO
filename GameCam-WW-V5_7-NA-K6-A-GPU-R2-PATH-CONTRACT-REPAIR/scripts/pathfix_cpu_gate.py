"""CPU-only gate for the unarmed K6-A R2 PATHFIX candidate."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "evidence"
CONTEXT = ROOT / "context"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def reject_execution(candidate, candidate_sha, authorization):
    if authorization is None:
        raise RuntimeError("NO_AUTHORIZATION_FILE")
    if authorization.get("authorized_launch_contract_sha256") != candidate_sha:
        raise RuntimeError("CONTRACT_SHA_MISMATCH")
    if candidate.get("model_execution_authorized") is not False or candidate.get("model_attempt_limit") != 0 or candidate.get("model_attempts") != 0:
        raise RuntimeError("CANDIDATE_NOT_UNARMED")
    raise RuntimeError("CPU_ONLY_CANDIDATE")


def run(output):
    output = Path(output)
    candidate_path = EVIDENCE / "PATH_11_new_launch_contract_candidate.json"
    candidate = load(candidate_path)
    candidate_sha = sha(candidate_path)
    checks = []

    def check(name, passed, detail=None):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    def expect_reject(name, authorization, expected):
        try:
            reject_execution(candidate, candidate_sha, authorization)
        except RuntimeError as exc:
            checks.append({"name": name, "passed": expected in str(exc), "reason": str(exc), "traceback": traceback.format_exc()})
        else:
            checks.append({"name": name, "passed": False, "error": "execution was not rejected"})

    expect_reject("missing_authorization_rejected", None, "NO_AUTHORIZATION_FILE")
    expect_reject("wrong_contract_sha_rejected", {"authorized_launch_contract_sha256": "0" * 64}, "CONTRACT_SHA_MISMATCH")
    expect_reject("consumed_attempt_01_authorization_rejected", load(CONTEXT / "consumed_attempt_01_authorization.json"), "CONTRACT_SHA_MISMATCH")
    expect_reject("matching_hash_cannot_arm_cpu_candidate", {"authorized_launch_contract_sha256": candidate_sha}, "CPU_ONLY_CANDIDATE")

    static = load(EVIDENCE / "PATH_06_static_runtime_validation.json")
    config = load(EVIDENCE / "PATH_07_original_config_integrity.json")
    weights = load(EVIDENCE / "PATH_08_weight_integrity.json")
    inputs = load(EVIDENCE / "PATH_09_input_integrity.json")
    source = load(EVIDENCE / "PATH_10_new_runtime_source_manifest.json")
    preservation = load(EVIDENCE / "PATH_13_attempt_01_preservation.json")
    path_tests = load(EVIDENCE / "PATH_05_path_contract_tests.json")
    audit = load(EVIDENCE / "PATH_02_symlink_chain_audit.json")

    def audit_all_runtime_paths():
        pin = load(ROOT / "config" / "dependency_pins.json")
        rows = {r["path_linux"]: r for r in csv.DictReader((EVIDENCE / "PATH_01_all_path_identity_audit.csv").open(encoding="utf-8-sig", newline=""))}
        expected = {}
        def add(path, real):
            if path:
                expected[str(path)] = str(real)
        add(pin["config"]["path_linux"], pin["config"]["real_linux"])
        add(pin["k4_live_contract"]["path_linux"], pin["k4_live_contract"]["real_linux"])
        for item in pin["weights"]:
            add(item["path_linux"], item["real_linux"])
        hf = pin["hf"]
        add(hf["ref_path_linux"], hf["ref_real_linux"])
        alias_root, real_root = audit["source_root_alias"], audit["source_root_resolved"]
        for item in pin["files"].values():
            add(alias_root + "/" + item["path"], real_root + "/" + item["path"])
        for item in pin.get("path_directories", []):
            add(item["path_linux"], item["real_linux"])
        for value in list(pin.get("environment", {}).values()) + list(pin.get("hub_models", {}).values()):
            if isinstance(value, str) and value.startswith("/mnt/"):
                add(value, audit["project_canonical"] + value[len(audit["project_alias"]):])
        with (ROOT / "config" / "k4_input_frames.csv").open(encoding="utf-8-sig", newline="") as stream:
            for item in csv.DictReader(stream):
                add(item["path_linux"], item["real_linux"])
        for case in load(ROOT / "config" / "cases.json"):
            add(case.get("rgb_folder_linux"), case.get("rgb_folder_real_linux"))
            for item in case.get("frames", []):
                add(item["path_linux"], item["real_linux"])
        bad = []
        for path, real in expected.items():
            row = rows.get(path)
            if row is None or row.get("status") != "PASS" or row.get("resolved_path_linux") != real:
                bad.append({"path": path, "expected_real_linux": real,
                            "status": row.get("status") if row else "NOT_AUDITED",
                            "resolved_path_linux": row.get("resolved_path_linux") if row else None})
        return {"passed": not bad, "active_runtime_paths": len(expected), "failures": bad}

    runtime_path_audit = audit_all_runtime_paths()

    check("v2_runtime_pin_hash", candidate["hashes"]["runtime_pins_sha256"] == sha(ROOT / "scripts" / "runtime_dependency_pins.py"), candidate["hashes"]["runtime_pins_sha256"])
    check("v2_dependency_pin_hash", candidate["hashes"]["dependency_pins_sha256"] == sha(ROOT / "config" / "dependency_pins.json"), candidate["hashes"]["dependency_pins_sha256"])
    check("runtime_source_manifest", source["passed"], source.get("summary"))
    check("path_audit_is_for_pathfix", "PATH-CONTRACT-REPAIR" in audit["source_root_alias"] and audit["review_required"] == 0, {k: audit[k] for k in ("audited_unique_paths", "pass", "review_required", "missing_or_invalid")})
    check("all_active_v2_paths_resolve_to_pinned_real_paths", runtime_path_audit["passed"], {"active_runtime_paths": runtime_path_audit["active_runtime_paths"], "failures": runtime_path_audit["failures"]})
    check("12_cpu_path_tests", path_tests["passed"] and path_tests["test_count"] == 12, {"count": path_tests["test_count"], "cuda_executed": path_tests["cuda_executed"]})
    check("original_config_sha", static["passed"] and config["passed"] and config["sha256"] == candidate["frozen_inputs"]["original_config_sha256"], config["sha256"])
    check("four_weight_hashes", weights["passed"] and len(weights["weights"]) == 4 and all(x["passed"] for x in weights["weights"]) and {x["id"]: x["sha256"] for x in weights["weights"]} == candidate["frozen_inputs"]["weights"], {"count": len(weights["weights"]), "deserialized": weights["checkpoint_deserialized"]})
    frame_match = len(inputs["frames"]) == len(static["input_frames"]) == 120 and all(all(a.get(k) == b.get(k) for k in ("ordinal", "published_frame", "path", "real_path", "bytes", "sha256")) for a, b in zip(inputs["frames"], static["input_frames"]))
    check("120_frame_hashes_and_records", inputs["passed"] and frame_match and inputs["input_frame_manifest_sha256"] == candidate["frozen_inputs"]["input_frame_manifest_sha256"], {"frames": len(inputs["frames"]), "range": [inputs["published_start"], inputs["published_end"]], "RGB_decoded": inputs["RGB_decoded"], "GT_read": inputs["GT_values_read"]})

    supervisor = load(EVIDENCE / "supervisor_cpu" / "07_supervisor_integration_tests.json")
    growth = load(EVIDENCE / "supervisor_cpu" / "08_memory_growth_guard_tests.json")
    normal = next(x["supervisor_result"] for x in supervisor["tests"] if x["fault"] == "normal")
    check("CPU_supervisor_and_monitor_barrier", supervisor["passed"] and normal["execution_kind"] == "cpu_dummy" and normal["startup_barrier_passed"] and normal["worker_fully_exited"] and normal["monitor_fully_exited"] and normal["model_attempts"] == 0 and growth["passed"] and growth["real_GPU_memory_pressure_used"] is False, {"scenarios": len(supervisor["tests"]), "growth_tests": len(growth["tests"]), "real_gpu_pressure": growth["real_GPU_memory_pressure_used"]})
    check("attempt_01_manifest_preserved", preservation["passed"] and preservation["verified_file_count"] == 24 and preservation["new_attempts_created"] == 0, {"files": preservation["verified_file_count"], "attempt_number": preservation["attempt_number"]})
    check("512MiB_no_retry_safety", candidate["safety"]["minimum_free_memory_MiB"] == 512 and candidate["automatic_retry"] is False and candidate["hashes"]["original_safety_contract_sha256"] == sha(CONTEXT / "original_safety_contract_manifest.json"), candidate["safety"])
    check("candidate_unarmed", candidate["model_execution_authorized"] is False and candidate["model_attempt_limit"] == 0 and candidate["model_attempts"] == 0 and candidate["automatic_retry"] is False, {k: candidate[k] for k in ("model_execution_authorized", "model_attempt_limit", "model_attempts", "automatic_retry")})
    check("no_new_attempt_file", not (ROOT / "model_attempt.json").exists(), {"model_child_spawned": False, "new_attempts_created": 0})

    passed = all(x["passed"] for x in checks)
    report = {"suite": "K6-A-GPU-R2-PATHFIX CPU-only dry run", "passed": passed, "checks": checks, "check_count": len(checks), "candidate_sha256": candidate_sha, "model_execution_authorized": False, "model_attempt_limit": 0, "model_attempts": 0, "automatic_retry": False, "model_child_spawned": False, "checkpoint_deserialized": False, "torch_imported": "torch" in sys.modules, "model_constructed": False, "cuda_executed": False, "cuda_work_permit_written": False, "real_images_decoded": False, "GT_values_read": False, "prior_attempt_count": 1, "new_attempts_created": 0}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = json.dumps({"passed": passed, "checks": len(checks), "candidate_sha256": candidate_sha, "model_attempts": 0, "model_child_spawned": False, "torch_imported": report["torch_imported"], "cuda_executed": False}, ensure_ascii=False)
    output.with_name(output.stem + ".stdout.txt").write_text(summary + "\n", encoding="utf-8")
    output.with_name(output.stem + ".stderr.txt").write_text("", encoding="utf-8")
    print(summary, flush=True)
    return 0 if passed else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        return run(args.output)
    except BaseException:
        output = Path(args.output)
        detail = traceback.format_exc()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"passed": False, "fatal_traceback": detail, "model_execution_authorized": False, "model_attempt_limit": 0, "model_attempts": 0, "model_child_spawned": False, "cuda_executed": False, "new_attempts_created": 0}, indent=2) + "\n", encoding="utf-8")
        output.with_name(output.stem + ".stdout.txt").write_text("", encoding="utf-8")
        output.with_name(output.stem + ".stderr.txt").write_text(detail, encoding="utf-8")
        sys.stderr.write(detail)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
