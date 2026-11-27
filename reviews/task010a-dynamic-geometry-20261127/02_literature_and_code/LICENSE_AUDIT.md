# License and redistribution inventory

Exact source versions, retrieval dates and archive hashes: `SOURCE_SNAPSHOTS.json`.

| Root repository | Root declaration | Additional boundary |
|---|---|---|
| GMOS | Apache-2.0 | Vendored Pi3 explicitly limits use to non-commercial purposes; some positional code has CC-BY-NC-SA notices. Root license is not a blanket grant for nested components/weights. |
| GeoMotion | MIT | Pi3-derived components and external SAM2/RAFT retain their own notices; weight terms remain separate. |
| RoMo | Apache-2.0 | SAM2 and optical-flow dependencies retain upstream licenses. |
| DynOSeg | BSD-3-Clause | Repository currently lacks a runnable implementation/weight. |
| DYNAPO | No root license detected in inspected metadata | Do not redistribute its source or claim a license was established. No execution required here. |
| MonST3R | Custom/NOASSERTION in GitHub metadata | Source and dependency notices must be examined individually before redistribution; not included as copied production code. |
| SAM2 | Apache-2.0 | Official source snapshot used as dependency reference. |
| DROID-W | Apache-2.0 root | Original baseline and compiled extension are read-only; this task publishes only isolated adapters and evidence. |

The review distribution excludes checkpoint binaries, vendored model source snapshots, raw datasets and environment binaries. Official source/weight URLs and observed hashes are provided for reconstruction. No commercial-usage suitability claim is made.
