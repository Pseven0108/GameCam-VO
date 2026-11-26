"""Package the complete local environment evidence, excluding installation binaries."""
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "GAMECAM_LOCAL_RTX5060_ENVIRONMENT_REVIEW.zip"


def main():
    boundary = {
        "local_environment_only": True, "research_models_loaded": False,
        "real_RGB_or_GT_read": False, "checkpoint_deserialized": False,
        "real_SLAM_or_training_executed": False, "custom_CUDA_extension_compiled": False,
        "remote_GPU_started_or_used": False, "remote_instance_restarted_or_stopped": False,
        "original_package_versions_preserved": True, "original_baseline_modified": False,
        "excluded": ["downloaded installation wheels", "temporary download/extraction files",
                     "credentials", "raw datasets", "model weights", "environment binaries"],
        "publication_authorized_by_user_standing_delivery_preference": True,
    }
    (ROOT / "AUTHORIZATION_AND_SCOPE.json").write_text(json.dumps(boundary, indent=2)+"\n", encoding="utf-8")
    excluded = {"downloads", "temp", "deliveries", "publication", "__pycache__"}
    paths = sorted(p for p in ROOT.rglob("*") if p.is_file() and not (set(p.relative_to(ROOT).parts) & excluded))
    if any(p.name == "FILE_SHA256_MANIFEST.json" for p in paths):
        raise FileExistsError("Preserve prior manifest")
    records = []
    secrets = re.compile(rb"(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (?:OPENSSH|RSA|EC) PRIVATE KEY-----)")
    for path in paths:
        data = path.read_bytes()
        if secrets.search(data):
            raise ValueError("Publication secret scan failed: " + path.name)
        records.append({"path": path.relative_to(ROOT).as_posix(), "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest()})
    manifest = ROOT / "FILE_SHA256_MANIFEST.json"
    manifest.write_text(json.dumps({"algorithm": "SHA256", "manifest_self_excluded": True,
                                   "files": records}, indent=2)+"\n", encoding="utf-8")
    paths.append(manifest)
    directory = ROOT / "deliveries"
    directory.mkdir(exist_ok=False)
    archive = directory / NAME
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in paths:
            z.write(path, path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(records) + 1
        for record in records:
            data = z.read(record["path"])
            assert len(data) == record["bytes"]
            assert hashlib.sha256(data).hexdigest() == record["sha256"]
    receipt = {"ZIP_name": NAME, "ZIP_bytes": archive.stat().st_size,
               "ZIP_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
               "ZIP_members": len(paths), "internal_SHA256_entries": len(records),
               "CRC": "PASS", "internal_SHA256": "PASS",
               "all_evidence_included_except_declared_installation_binaries": True}
    (directory / "PACKAGE_VERIFICATION.json").write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")
    (directory / (NAME+".sha256")).write_text(receipt["ZIP_sha256"]+"  "+NAME+"\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
