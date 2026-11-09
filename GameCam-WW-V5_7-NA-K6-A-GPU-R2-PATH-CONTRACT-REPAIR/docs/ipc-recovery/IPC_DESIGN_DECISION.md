# Session-owned Arena design

The owning Supervisor creates `/dev/shm/gamecam-ipc/<bound-session>` with mode0700 after a fresh authorization claim and before Worker creation. It binds session, UID, supervisor PID, canonical run directory and device/inode of the IPC root and fallback in a mode0600 marker.

The Worker verifies this binding and installs a process-local Arena directory chooser before the first Value/Array allocation. It refuses preexisting Arena allocations. Shared-memory capacity is checked against the allocation size; only the same run's `tmp` can be selected as fallback. TMPDIR and tempfile.tempdir are changed only in that Worker process. No installed stdlib, global environment or other process is modified.

The Python audit hook treats IPC separately from generic output roots. It admits only exclusive Arena creation/read and unlink with the current PID and exact tempfile name format. Other sessions, symlink paths, mkdir/rename/link/chmod/symlink creation in the IPC root, generic /tmp and generic /dev/shm writes are rejected. An existing Arena file must be owned by the UID, regular, and mode0600. The stdlib mkstemp creation mode is0600.

After Worker and Monitor exit, only the owning Supervisor validates both root and fallback before deleting recognized files for its owned PIDs. Unknown residuals and replaced directories fail closed and are preserved. Setup failure removes only its newly created entries. No recursive deletion is used. The empty session tmp remains with the audit output; the exact IPC session directory is removed.

Limits: Python audit hooks are not an OS sandbox. Native POSIX semaphores, C-level file syscalls, mmap access and already-open descriptors are not comprehensively intercepted. Both fork and spawn semantics and post-exit semaphore cleanup were tested. Forced fallback can move Arena backing to the data disk and may add I/O; this is not a performance guarantee for SLAM.
