#!/bin/sh
set -eu
ROOT=/mnt/d/aaa/GameCam-VO-TASK009
export TMPDIR="$ROOT/runtime/tmp"
export CUDA_HOME="$ROOT/runtime/cuda128"
export PATH="$ROOT/runtime/wsl310/bin:$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/targets/x86_64-linux/lib:${LD_LIBRARY_PATH:-}"
export TORCH_HOME=/mnt/d/aaa/caches/torch
export HF_HOME=/mnt/d/aaa/caches/huggingface
export XDG_CACHE_HOME="$ROOT/runtime/cache"
export MPLCONFIGDIR="$ROOT/runtime/cache/matplotlib"
export TORCHINDUCTOR_CACHE_DIR="$ROOT/runtime/inductor"
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT:$ROOT/external/DROID-W:$ROOT/external/DROID-W/thirdparty/lietorch:${PYTHONPATH:-}"
mkdir -p "$TMPDIR" "$MPLCONFIGDIR"
cd "$ROOT"
exec python -B "$@"
