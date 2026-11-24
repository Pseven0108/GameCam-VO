# TASK004C-B-CONFIGDICT-CLOSURE — Final review

**Status: CONFIGDICT_REPAIRED; FULL_MODEL_CPU_RESTORE_BLOCKED_BY_TIMM_FORMAT.**

ConfigDict mapping loss and allocation are fixed in candidate commit `aa0cca3ed0d6e5d381422d8219234b8c0c6ad065`, from `a324b57760fdaf4929385f2271991d773533799d`. Only the snapshot module and the new ConfigDict adapter changed. The Metric3D identity adapter remains byte-identical.

| Check | Actual evidence |
|---|---|
| ConfigDict targeted tests | 14/14 PASS, exit 0 |
| Historical regression | 152/152 PASS, exit 0 |
| Actual-model ConfigDict subgraph | 6 ConfigDict objects; 24 reachable graph nodes; exact normalized mapping/attribute/reference graph PASS |
| Source real-weighted model fixed-input outputs | SHA values equal to historical reference |
| Complete real-model fresh-process restore | FAIL, exit 1 after 271.928 seconds |
| Restored forward, gradient, all-storage/47-family comparison | NOT_REACHED |
| New native GPU C0 | 0/2; no C0 exists |
| New short cross-D runs | 0/4 |
| New full B1/B2/B4/B3 runs | 0/4 |

The new failure is `timm.layers.format:Format`, specifically FiT3D `patch_embed.output_fmt = Format.NHWC`. The decoder treats it as a generic object and rejects `object.__new__` for its str/Enum subclass. This field is outside ConfigDict and existed in the historical snapshot. timm uses member identity (`is`), so converting to a string would change behavior. The complete model gate remains failed even though ConfigDict itself is now demonstrated.

The new authorization provides two ConfigDict-specific repair rounds. One was used; one remains. We did not use that budget to add a different FiT3D/timm adapter. This is a new scope boundary, not repair-budget exhaustion and not a GPU failure. No CUDA context was initialized by this task. The allocated RTX3090 is still online; it was not rebooted or shut down.

Historical snapshot protection was rechecked after failure: all 798 payload hashes and both metadata checks pass (800 files). Four original weights, R2 YAML and CUDA extension still match their locks. The new CPU fixture is retained with its raw logs and failure receipts. No Tensor payloads, weights, RGB, GT, arenas or SSH connection information are included in the public review.

The next narrowly scoped repair is a pinned exact-class enum adapter followed by the full strict fresh-process test. After that, authorized continuation still requires tested stage-qualified RGB019 processing, short80 schedules and formal487 native Final BA/Filler support before sealing a source-pinned C0. Existing bounded runner cannot honestly be called a completed formal runner.

No new causal, trajectory-accuracy or scale-improvement result was produced. Consult the detailed source audit, test report, full-model failure log, graph-origin JSON, CPU final gate and storage report.
