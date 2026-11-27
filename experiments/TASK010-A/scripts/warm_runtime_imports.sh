#!/bin/sh
set -eu
ROOT=/mnt/d/aaa/GameCam-VO-TASK010-A
RUNTIME=/mnt/d/aaa/GameCam-VO-TASK009/runtime
export TMPDIR=/mnt/d/aaa/tmp/gamecam-vo
export CUDA_HOME="$RUNTIME/cuda128"
export PATH="$RUNTIME/wsl310/bin:$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/targets/x86_64-linux/lib:${LD_LIBRARY_PATH:-}"
export TORCH_HOME=/mnt/d/aaa/caches/torch
export HF_HOME=/mnt/d/aaa/caches/huggingface
export XDG_CACHE_HOME=/mnt/d/aaa/caches/task010a
export MPLCONFIGDIR=/mnt/d/aaa/caches/task010a/matplotlib
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=0
export PYTHONPYCACHEPREFIX=/mnt/d/aaa/caches/task010a/wsl_pycache
export PYTHONPATH="$ROOT:$ROOT/experiments/TASK010-A/scripts:/mnt/d/aaa/GameCam-VO-TASK009/external/DROID-W:/mnt/d/aaa/GameCam-VO-TASK009/external/DROID-W/thirdparty/lietorch:${PYTHONPATH:-}"
mkdir -p "$TMPDIR" "$MPLCONFIGDIR"
cd "$ROOT"
exec python "$@"
