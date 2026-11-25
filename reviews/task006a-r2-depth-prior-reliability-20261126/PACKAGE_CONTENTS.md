# Package scope and checksum convention

The original ZIP contains every relevant new R2 script, report, result CSV/JSON,
figure, selected source snapshot and raw execution receipt in this review payload.
No model weights or complete raw dataset is copied. The small RGB/GT audit figure
is explicitly a data-alignment exhibit, not a prediction result.

Local isolated runtime_site packages and literature_cache full-text copies are
not redistributed. EXCLUDED_SUPPORT_ASSETS.json lists their identity and reason;
paper URL/SHA receipts and package versions remain reproducible in the payload.
No completed model experiment output is omitted: there was no model inference.

SHA256_MANIFEST.csv covers all payload files except that CSV and the JSON manifest.
FILE_SHA256_MANIFEST.json covers those files plus the CSV. It excludes itself to
avoid a recursive checksum. ZIP CRC checks every archive member. The original ZIP
SHA is recorded separately in deliveries and at review_packages on GitHub.
Deliveries/readback receipts are external to the sealed payload, avoiding self-reference.
