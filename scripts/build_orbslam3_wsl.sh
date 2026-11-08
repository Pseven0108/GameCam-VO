#!/usr/bin/env bash
# Run inside the existing Ubuntu WSL distribution; one compiler process bounds memory.
set -euo pipefail
cd /mnt/d/aaa/GameCam-VO
orbroot="$PWD/baselines/orb_slam3"
test "$(git -C "$orbroot/upstream" rev-parse HEAD)" = 0df83dde1c85c7ab91a0d47de7a29685d046f637
test "$(git -C "$orbroot/pangolin" rev-parse HEAD)" = dd801d244db3a8e27b7fe8020cd751404aa818fd
python3 - <<'PY'
from pathlib import Path
p = Path('baselines/orb_slam3/upstream/CMakeLists.txt')
s = p.read_text()
s = s.replace('find_package(OpenCV 4.4)', 'find_package(OpenCV 4.2)')
s = s.replace('OpenCV > 4.4 not found.', 'OpenCV >= 4.2 not found (GameCam build compatibility).')
p.write_text(s)
PY
git -c core.filemode=false -C "$orbroot/upstream" diff -- CMakeLists.txt > "$orbroot/opencv42_build_only.patch"
cmake -S "$orbroot/pangolin" -B "$orbroot/build-pangolin" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$orbroot/install" \
  -DBUILD_TESTS=OFF -DBUILD_TOOLS=OFF -DBUILD_EXAMPLES=OFF \
  -DBUILD_PANGOLIN_PYTHON=OFF -DBUILD_PYPANGOLIN_MODULE=OFF \
  -DBUILD_PANGOLIN_VIDEO=OFF -DBUILD_PANGOLIN_LIBOPENEXR=OFF
cmake --build "$orbroot/build-pangolin" --parallel 1
cmake --install "$orbroot/build-pangolin"
cmake -S "$orbroot/upstream/Thirdparty/DBoW2" -B "$orbroot/build-dbow2" -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=14
cmake --build "$orbroot/build-dbow2" --parallel 1
# Match upstream build.sh: g2o's explicit .so path is not a root-target dependency.
cmake -S "$orbroot/upstream/Thirdparty/g2o" -B "$orbroot/build-g2o" -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=14
cmake --build "$orbroot/build-g2o" --parallel 1
# Sophus is header-only for this library target.
cmake -S "$orbroot/upstream" -B "$orbroot/build-orbslam3" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=14 -DCMAKE_PREFIX_PATH="$orbroot/install"
cmake --build "$orbroot/build-orbslam3" --target ORB_SLAM3 --parallel 1
if [ ! -f "$orbroot/upstream/Vocabulary/ORBvoc.txt" ]; then
  tar -xf "$orbroot/upstream/Vocabulary/ORBvoc.txt.tar.gz" -C "$orbroot/upstream/Vocabulary"
fi
cmake -S "$orbroot" -B "$orbroot/build-runner" -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$orbroot/install"
cmake --build "$orbroot/build-runner" --parallel 1
