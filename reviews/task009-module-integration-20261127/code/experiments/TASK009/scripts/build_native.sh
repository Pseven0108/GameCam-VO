#!/bin/sh
set -eu
ROOT=/mnt/d/aaa/GameCam-VO-TASK009
export TMPDIR="$ROOT/runtime/tmp"
export CUDA_HOME="$ROOT/runtime/cuda128"
export PATH="$CUDA_HOME/bin:$ROOT/runtime/wsl310/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/targets/x86_64-linux/lib:${LD_LIBRARY_PATH:-}"
export TORCH_CUDA_ARCH_LIST=12.0
export MAX_JOBS=1
export TORCH_EXTENSIONS_DIR="$ROOT/runtime/torch_extensions"
export PYTHONDONTWRITEBYTECODE=1
export CPLUS_INCLUDE_PATH="$ROOT/runtime/python310/python/include/python3.10:${CPLUS_INCLUDE_PATH:-}"
for headers in "$ROOT"/runtime/wsl310/lib/python3.10/site-packages/nvidia/*/include; do
  if [ -d "$headers" ]; then export CPLUS_INCLUDE_PATH="$headers:$CPLUS_INCLUDE_PATH"; fi
done
export CFLAGS="-g0"
export CXXFLAGS="-g0"
export CC=gcc
export CXX=g++
export LDSHARED="g++ -shared"
export TASK009_LIETORCH_CORE_ONLY=1
if [ ! -e "$CUDA_HOME/targets/x86_64-linux/lib/libcudart.so" ]; then
  ln -s libcudart.so.12 "$CUDA_HOME/targets/x86_64-linux/lib/libcudart.so"
fi
if [ ! -e "$CUDA_HOME/include" ]; then
  ln -s targets/x86_64-linux/include "$CUDA_HOME/include"
fi
if [ ! -e "$CUDA_HOME/lib64" ]; then
  ln -s targets/x86_64-linux/lib "$CUDA_HOME/lib64"
fi
if [ ! -e "$CUDA_HOME/targets/x86_64-linux/nvvm" ]; then
  ln -s ../../nvvm "$CUDA_HOME/targets/x86_64-linux/nvvm"
fi
cd "$ROOT/external/DROID-W/thirdparty/lietorch"
python setup.py build_ext --inplace
cd "$ROOT/external/DROID-W"
python setup.py build_ext --inplace
