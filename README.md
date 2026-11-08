# GameCam-VO

This repository records a filtered, dated source snapshot of the GameCam-VO project and its reviewed DROID-W baseline sources.

The `v0.1.0-baseline` source snapshot is captured from the cloud production tree as of 2026-11-09. That tree had no Git metadata, so this tag does not identify the code revision of any historical model run. See [Baseline Provenance](docs/BASELINE_PROVENANCE.md) for the source comparison, exclusions, and limitations.

Datasets, model checkpoints, and generated experiment outputs are not included in this repository. Their identities and locations remain external to the source snapshot.

The root project environment declares Python 3.11 in `pyproject.toml` and `environment.yml`. DROID-W's vendored upstream documentation describes a separate Python 3.10/CUDA 11.8 environment. These instructions are not a verified unified runtime setup.

No GPU experiment result is implied by this baseline. The source snapshot has not yet passed the RuntimePins V2 production-launcher, loader, Supervisor, and CPU data-pipeline gates required for a GPU-ready candidate.
