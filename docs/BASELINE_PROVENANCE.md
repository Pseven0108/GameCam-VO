# Baseline Provenance

## Identity

This repository baseline is a dated source snapshot captured on 2026-11-09 from the cloud production directory `/root/rivermind-data/gamecam/GameCam-VO` on host `jupyter-u313cp7kyztcpsz8`. The production directory had no Git metadata, so no historical production commit can be recovered from it.

The baseline identifies the reviewed source snapshot only. It does not claim that this tree produced a successful DROID-W run, a completed SLAM trajectory, or a pose evaluation. Historical Attempt 01 stopped before importing Torch and processed 0/120 frames; it produced no pose.

## Source comparison

- The selected source inventory contained 4,104 cloud files. All 4,104 shared selected paths matched the local checkout by SHA-256; there were no common-path content mismatches or cloud-only paths.
- The local checkout had 47 local-only paths. Those files were not merged into this baseline.
- The staging selection contains 3,973 files totaling 37,695,681 bytes: 3,712 third-party baseline source files, 222 project source files, 17 RuntimePins snapshot files, 11 configuration/environment files, 7 test/fixture files, and 4 project metadata files.
- Dataset content, model checkpoints, binary assets, generated test artifacts, and the consumed Attempt 01 authorization record were excluded. The selection manifest and copy report are retained outside the Git tree in the audit bundle.
- The reviewed source-manifest SHA-256 is `01d9fd10c180ac0e2521fb394730c2828a15d1843db233ea7b42a377f4900d0c`. The underlying project-code manifest SHA-256 is `d6082e3097a06111544b46bd108baf2a93383e7813ed5688cc9442f35d032cd9`; the DROID-W payload manifest SHA-256 is `fb3e01da2da1ff0207e9dc4ec2a80652e31ba3eb5c246c79bded71bf1ec132ff`.

## Documentation and runtime limits

The cloud snapshot's original root README is preserved as [`cloud_snapshot_original_README.md`](cloud_snapshot_original_README.md), SHA-256 `d0fad1b2b6212207ebb3aea950658e50eeda4e3d780647c9f4c93e6cb579e6aa`. The root README was replaced with a concise description of this dated baseline because the original contained mutable project-status statements that are not evidence of the present experiment state.

The root `pyproject.toml` and `environment.yml` require Python 3.11 for the GameCam-VO project. The vendored DROID-W upstream README documents a separate Python 3.10/CUDA 11.8 setup. These are distinct environment claims; this baseline does not assert that the cloud runtime dependencies are reconciled or GPU-ready.

The PATHFIX snapshot contains RuntimePins V2 and CPU-only checks, but the historical audit explicitly recorded that the V2 gate was not integrated into a verified production model launcher. RuntimePins presence is not evidence that a real tracking run passed its launch, loader, or authorization gates.

## Git interpretation

The first Git commit and `v0.1.0-baseline` tag record this reviewed, filtered cloud source snapshot plus the provenance documentation. They must not be described as the commit used by the historical GPU attempt or as a validated SLAM runtime. The connection-test branch `codex-connection-check-20261108T204637Z` is independent and must be retained.

## Launch-chain closure supplement

A second read-only audit found 28 source/configuration files (207,400 bytes) outside the original selected source scope. These files were copied from their existing cloud locations with before/after SHA-256 verification, recorded separately in `launch_chain_supplement_manifest.csv`. Seven R1 scripts and three R2 environment/configuration files retain their production-relative paths; eighteen legacy cloud launch-audit scripts/configurations are preserved under `legacy_remote_launch_audit/` as references. No local-only file was merged. The baseline therefore includes 4,001 copied source files, plus provenance documentation and byte-preserving Git attributes. The legacy launch-audit references are not a new approved GPU launcher.
