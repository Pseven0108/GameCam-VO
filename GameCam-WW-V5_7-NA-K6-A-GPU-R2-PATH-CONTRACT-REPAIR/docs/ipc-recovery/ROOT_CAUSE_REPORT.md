# IPC boundary recovery root cause

The prior authorized run loaded droid.pth, then stopped before the first frame or a complete Tracker. Its authorization was consumed. This recovery executed no model.

The first exception was `MODEL_WRITE_OUTSIDE_OWN_OUTPUT:/dev/shm/pym-3374-978jmx53`. Actual upstream `baselines/droid_w/upstream/src/depth_video.py:34` constructs `Value('i', 0)`. On the audited Python 3.10.20 runtime, sharedctypes allocates BufferWrapper/Heap/Arena; Linux Arena._choose_dir prefers `/dev/shm` and calls tempfile.mkstemp there. TMPDIR only controls the fallback, so setting TMPDIR alone did not isolate that first allocation.

The later supervisor reason was `CUDA_MONITOR_STALE_OVER_3_SECONDS`. In the old adapter, Guard.finish stopped the CUDA heartbeat before the final result handoff and Python process exit. The still-live Worker then appeared stale. This second stop did not establish an OOM or a SLAM tracking failure.

Evidence: HISTORICAL_EVENT_TIMELINE.json, ROOT_CAUSE_SOURCE_AUDIT.json, actual stdlib and upstream call sites. Historical timestamps do not directly measure the instant the first exception was thrown.

The old candidate SHA remains `b425b1d8dc511f965b194aaa19e0b55e61c88cfaf3ec2fb62f2afc262e58fd0c`. All changes are in a separate clone and branch. No historical output, production source, weight or dataset was edited.
