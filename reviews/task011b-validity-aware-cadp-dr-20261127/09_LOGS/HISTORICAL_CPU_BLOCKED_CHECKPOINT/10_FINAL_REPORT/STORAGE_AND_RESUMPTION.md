# Storage and resumption

The20-window input list is already frozen and1280 originals are locally admitted. All archives and historical experiments remain intact. Current remote data free space is about11.13GiB; this is a measured checkpoint, not a future capacity guarantee.

Do not stage all20 windows' full priors and all140 outputs at once. Before actual GPU work measure the isolated extension build size, one-window native/flip/feature cache and one-group output. Preserve a10GiB remote reserve; calculate actual temporary compression and artifact overhead. If space is insufficient, stop with an explicit budget. Transfer newly generated task outputs to local D:, compare complete SHA/CRC and file identity, verify the owning process has exited, and only then remove that task's own temporary staged files under a documented lifecycle. Never automatically delete historical assets, weights, installed environments or frozen data.

GPU continuation order: current host/device/VRAM/process/SHM/disk identity → isolated compile → real native D0/D1 endpoint regression with original-repeat controls → common native-configuration prior cache/provider validation → all seven arms on the frozen20 windows → paired offline SE3/Sim3/RPE/scale analysis → complete final review. No automatic retries or protocol changes after OOM/native faults. No DROID-SLAM rerun or extra algorithm/data branch is part of this task.

The original buffer500 video logical storage alone is about6.955GiB before networks and workspaces. Therefore no assumption is made that the unchanged formal protocol fits the local8GB GPU, and no silent resolution/buffer/precision substitution is used. Keep the hardware division: local CPU work here; approved native/formal work on the available3090.
