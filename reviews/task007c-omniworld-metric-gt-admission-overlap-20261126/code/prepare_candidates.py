"""Read-only reuse of frozen metadata, captions and Others archives."""
import csv
import hashlib
import json
import math
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
OLD = PROJECT / "R6_VP1_OTHERS_FULL_DOWNLOAD_20261115"
UIDS = ["016d3596da27", "03b9161e3ff2", "0caf78b8eeac"]


def h(b): return hashlib.sha256(b).hexdigest()
def dump(p, data):
    p = ROOT / p; p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False); f.write("\n")


def main():
    meta = PROJECT / "GAMECAM_OWG_PREFLIGHT_20261115/evidence/omniworld_game_metadata.csv"
    b = meta.read_bytes()
    assert len(b) == 66930 and h(b) == "460ad6d26f775b265da462be679fa96bff6df4e4211a66a9b2aa7d303a826fdf"
    assert hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest() == "00b580ead4422f315800191127cf749b38eff697"
    metadata = list(csv.DictReader(b.decode("utf-8-sig").splitlines()))
    mp = PROJECT / "GAMECAM_OWG_PREFLIGHT_20261115/01_DATASET_INVENTORY/OWG_REMOTE_FILE_MANIFEST.csv"
    archive_rows = list(csv.DictReader(mp.open(encoding="utf-8-sig", newline="")))
    protected = [{"path": str(meta), "bytes": len(b), "sha256": h(b)}, {"path": str(mp), "bytes": mp.stat().st_size, "sha256": h(mp.read_bytes())}]
    result = []
    for uid in UIDS:
        rows = [r for r in metadata if r["UID"] == uid]
        assert len(rows) == 1
        row = rows[0]; scale = float(row["Metric Scale"])
        assert math.isfinite(scale) and scale > 0
        ar = [r for r in archive_rows if uid in r["path"]]
        others_row = next(r for r in ar if r["path"].endswith("_others.tar.gz"))
        others = OLD / "02_ARCHIVES" / others_row["path"]
        payload = others.read_bytes()
        assert len(payload) == int(others_row["bytes"]) and h(payload) == others_row["lfs_sha256"]
        protected.append({"path": str(others), "bytes": len(payload), "sha256": h(payload)})
        members = {}
        with tarfile.open(others, "r:gz") as z:
            for name in ["fps.txt", "split_info.json", "camera/split_0.json", "text/000001_000081.json"]:
                matches = [m for m in z.getmembers() if m.name == name]
                assert len(matches) == 1 and matches[0].isfile()
                members[name] = z.extractfile(matches[0]).read()
        split = json.loads(members["split_info.json"])
        frames = split["split"][0]
        assert len(frames) >= 3 and frames == sorted(set(frames))
        ids = frames[:3]
        assert ids == [0, 1, 2], "No substitute or more distant prefix acquisition"
        test_ids = [int(i) for i in row["Test Split Index"].split(",") if i.strip()]
        assert 0 not in test_ids, "Do not use an official held-out split for future calibration"
        camera = json.loads(members["camera/split_0.json"])
        assert len(camera["quats"]) == len(camera["trans"]) == len(frames)
        caption = json.loads(members["text/000001_000081.json"])
        # Select from already sealed explicit TP classification; never infer its
        # truth from UID or Metric Scale, and verify RGB only after acquisition.
        cls = OLD / "04_VIEWPOINT_CLASSIFICATION/OWG_FULL_TP_FOLLOW_CANDIDATES.csv"
        matches = [r for r in csv.DictReader(cls.open(encoding="utf-8-sig", newline="")) if r["uid"] == uid and r["filename"] == "000001_000081.json"]
        assert len(matches) == 1 and matches[0]["viewpoint_family"] == "TP"
        assert matches[0]["sha256"] == h(members["text/000001_000081.json"])
        for name, content in members.items():
            p = ROOT / "raw_inputs" / uid / name; p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("xb") as f: f.write(content)
        use = [next(r for r in ar if r["path"].endswith(suffix)) for suffix in ["_depth_0000.tar.gz", "_rgb_0000.tar.gz"]]
        result.append({"uid": uid, "metric_scale": scale, "metric_scale_row_unique": True,
            "source_metadata": row, "split_index": 0, "frames": ids, "first_split_length": len(frames),
            "not_official_test_split": True, "caption_class": "TP_FOLLOW_TEXT_ONLY", "viewpoint_visually_verified": False,
            "caption_sha256": h(members["text/000001_000081.json"]),
            "caption_evidence": json.loads(matches[0]["evidence"]),
            "others_archive": {"path": str(others), "bytes": len(payload), "sha256": h(payload)},
            "local_metadata_members": [{"path": n, "bytes": len(c), "sha256": h(c)} for n, c in members.items()],
            "needed_archives": use, "candidate_selection_uses_model_errors": False})
    dump("evidence/CANDIDATE_INTAKE.json", {"candidates": result, "new_payload_downloaded_bytes": 0,
         "official_metric_scale_source_row_check": "PASS", "independent_physical_accuracy": "NOT_ESTABLISHED_FROM_CSV_ALONE"})
    dump("evidence/INPUT_PRESERVATION_BEFORE.json", {"files": protected, "all_hashes_checked": True})
    print(json.dumps({"UIDs": UIDS, "samples_planned": 9, "all_first_ids": [r["frames"] for r in result],
          "scales": [r["metric_scale"] for r in result], "reused_others_archives_verified": 3}, indent=2))


if __name__ == "__main__": main()
