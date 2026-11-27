#!/bin/sh
set -eu
PIDFILE=/mnt/d/aaa/GameCam-VO-TASK010-A/experiments/TASK010-A/private/wsl_runtime_hold.pid
if [ "${1:-start}" = stop ]; then
    python_pid=$(cat "$PIDFILE")
    case "$python_pid" in ''|*[!0-9]*) exit 2;; esac
    if [ -r "/proc/$python_pid/cmdline" ]; then
        command_name=$(tr '\000' ' ' < "/proc/$python_pid/cmdline")
        [ "$command_name" = "sleep 10800 " ] || exit 3
        kill -TERM "$python_pid"
    fi
    exit 0
fi
echo "$$" > "$PIDFILE"
exec sleep 10800
