# TASK011E — authorized formal experiment

Status: RUNNING_PRIOR_CACHE_GENERATION.

Release baseline: `ae5d98cf339b4ea867193362f384fe5a17737f26`.
Approved: 19 common caches (2432 Metric3D forwards), then 285 serial E2E jobs from the unchanged EXECUTION_ORDER.csv. The first 15 are the engineering canary and count toward the 285. No FSR is authorized at this stage.

Fast GPU gate passed on the allocated RTX3090 with PyTorch 2.1.0+cu118. The 500-slot, 45x80 A7 adapter remains on GPU and transfers only its compact statistics packet. All four actually loaded weight files match their sealed hashes.

The official DROID-W deployment is an archive with `.official_archive.json`, not a Git checkout. Commit provenance is c3414af6; all 102 frozen Python/config files and the installed original extension remain hash-verified. TASK011E alone accepts this archive identity without editing the frozen source.

Secondary thresholds remain unapproved and descriptive-only. Runtime permission is explicit and bound to the user instruction, protocol, implementation lock, weight identity and job key. Unknown actions, FSR, unknown jobs, corrupted terminal evidence, unfinished attempts and engineering failures fail closed.

Each snapshot and cache write preserves a 10 GiB free-space floor. No historical result is deleted. A0 records all qualifying snapshots, their cumulative bytes and observer cost separately. A storage stop is an actual stop, not an automatic retry.

Progress is read from private/PROGRESS_READS.jsonl and the remote batch checkpoint. Partial results are not confirmatory aggregate evidence. Original TASK011B/C/D source, artifacts and releases are preserved.
