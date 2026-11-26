# Complete review payload

All 16 original model-output NPZ files, including the real smoke raw-bin logits,
are inside the original ZIP. Configs, scripts, failed and successful stage logs,
GT source/hash manifests, strict-gate failure, secondary diagnostic protocols and
results, tests, figures and source snapshots are included. Raw input datasets and
model weights are not redistributed; their identities and locations are indexed.

SHA256_MANIFEST.csv covers payload except both manifests. The JSON manifest also
covers the CSV and excludes itself to avoid recursion. ZIP CRC covers every member;
the external ZIP SHA covers the whole original archive. Delivery/publication receipts
are outside the sealed payload. Any omitted Git files are enumerated in publication
metadata; complete raw model outputs remain in the original full review ZIP asset.
