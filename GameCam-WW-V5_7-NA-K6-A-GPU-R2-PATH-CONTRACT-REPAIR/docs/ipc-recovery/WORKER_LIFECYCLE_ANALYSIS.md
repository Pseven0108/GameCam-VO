# Worker termination lifecycle

Old order: exception -> Guard.finish stops heartbeat -> final result -> Python teardown -> CUDA age exceeds three seconds -> Supervisor SIGTERM. The first error was obscured by the later supervision reason.

New order: snapshot resources while heartbeat remains active -> save final result -> publish atomic terminal file bound to session/PID/kind/result hash/status/frame counts/time -> Guard.finish -> bounded process exit observation -> monitor exit -> owner IPC cleanup.

WORKER_RUNNING retains the exact three-second CUDA and NVML freshness checks. Only a validated terminal handoff enters WORKER_TERMINAL_CLEANUP. NVML, worker exit, overall timeout and supervisor heartbeat remain active. Cleanup observation is five seconds; a hang triggers SIGTERM, the unchanged five-second grace, and SIGKILL if needed. The primary model error and the cleanup reason are separate fields.

CPU coverage includes all fourteen required failure categories, terminal tampering, NVML staleness during cleanup, four-second delayed exit, SIGTERM-ignoring hang, parent loss, and invalid terminal records. All real fixture processes were reaped. No fixture deserialized a checkpoint or instantiated Tracker.

A crash before terminal publication is still a crash. It does not gain a terminal-state exemption from freshness checks. The protocol coordinates trusted code inside the worker; it is not proof against arbitrary native code falsifying files.
