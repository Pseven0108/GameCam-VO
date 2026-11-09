# Source Origin Analysis

Captured 2026-11-09 (Asia/Shanghai).
Decision: `CLOUD_PRODUCTION_SNAPSHOT_BASELINE`; not a claim of a completed GPU model run.

## Provenance

- Cloud host/root: `jupyter-u313cp7kyztcpsz8` / `/root/rivermind-data/gamecam/GameCam-VO`.
- The cloud project root has no `.git` metadata and therefore no recoverable production-root commit.
- Local checkout: `D:/aaa/GameCam-VO`, branch `repro/2026-11-01-phase5`, HEAD `388fedf14ab1a071ab9c6955174ff092589300f3`; 6 tracked changes and 126,805 expanded untracked files. It was not used as the Staging copy source.
- The completed source comparison covers 4,151 selected local files and 4,104 selected cloud files: 4,104 exact matches, 47 local-only, no remote-only, and no common-path content mismatches. All 47 local-only entries remain separate and were not merged.
- `R2_project_code_manifest.json` SHA-256: `d6082e3097a06111544b46bd108baf2a93383e7813ed5688cc9442f35d032cd9`. All 244 project source/config/test-source files match locally and on the cloud. The other 621 entries are generated `tests/_artifacts` and are excluded.
- `R2_payload_manifest.json` SHA-256: `fb3e01da2da1ff0207e9dc4ec2a80652e31ba3eb5c246c79bded71bf1ec132ff`. All 3,842 third-party baseline source files match its hashes. Payload entries outside the source inventory are not copied.

## Attempt 01

Attempt 01 remains unchanged and its 24-file delivery manifest re-verifies. Its one-shot authorization was consumed. The worker stopped at the runtime path-contract check before `import torch`; it processed 0/120 frames and produced no pose. The launch-contract hash is not a Git commit or a complete source-tree identity. The new baseline tag will identify only the dated cloud production snapshot, not a successfully executed SLAM build.

## Path audit

- The root PATHFIX audit consumed by `pathfix_cpu_gate.py`: 162 paths, 147 PASS, 0 REVIEW_REQUIRED, 15 inherited missing references. The CPU gate report confirms 140/140 active V2 paths and 18/18 gate checks pass.
- A nested `path_audit_v2` snapshot has 6 REVIEW_REQUIRED alias mismatches for the K4 contract, K5.1 config, and four weight paths. Sizes, hashes, and allowed roots passed; the old `/mnt/d/aaa/...` `real_linux` values did not equal canonical `/root/rivermind-data/...` resolutions. The root post-fix audit records the canonical paths and is the audit used by the CPU gate. The nested report is retained as historical evidence.
- The 15 missing paths are classified in `historical_path_classification.csv`; they are retained and not silently substituted. RuntimePins V2 does not dereference these inherited path strings.

## Decision

The cloud tree can be published as a dated source snapshot. Historical runtime commit identity remains `NOT_ESTABLISHED`; neither the new baseline commit nor its tag may be described as the source of a successful GPU run.

## Final preservation

Selected cloud source/config files: 4100 unchanged; supplemental source origins: 28 unchanged; local selected hashed files: 4,147 unchanged; Attempt 01: 24/24 unchanged. Each initial inventory contains four metadata entries without byte hashes; those are not counted as hashed files.
