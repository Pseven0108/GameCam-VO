# TASK011E R3 startup repair and explicitly approved retry

User request (2026-11-28): 修复，然后自己重跑实验.

The sealed R2 first formal job failed because spawned children resolved generic `common` to TASK011B. R3 authorization and native identity checks now import the unique stage-local `task011e_io`. It preserves the original SHA-256 byte contract and does not replace the other task's `common` module.

A daemon observer monitors only the native driver's registered child processes. Nonzero child exit produces a structured receipt and exits the waiting driver with code70. The independent Linux launcher creates a private session and cleans up only this session's remaining processes. It does not time out, retry, alter BA, or terminate another GPU user's process.

The scientific controller, original RGB preprocessing, original checkpoint/configuration, native extension, collector, metrics, order and parameters are unchanged. Model and source hashes passed; R1/R2 are preserved. The user-authorized retry is in an independent R3 directory; a fresh engineering failure still stops the batch.

Real local CPU regression: 10 passed, 1 Linux-only skipped. Real Linux server CPU regression: 11 passed, 0 skipped. Model loading and SLAM were not used for these synthetic startup tests. Native formal runtime verification is reported separately from CPU tests.

All19 sealed common caches (1216NPZ) were rehashed and reused; no cache model forward was added in R3. Keep the failed R2 engineering attempt as extra history, not as a successful scientific run. No aggregate effectiveness conclusion until the full planned285 unique jobs have legal terminals.
