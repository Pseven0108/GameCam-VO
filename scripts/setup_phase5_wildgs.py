"""Build WildGS's own backend in its isolated prefix; preserve prior envs."""
from __future__ import annotations

import _bootstrap
import hashlib
import json
import re
import subprocess
import time

from gamecam_vo.common import PROJECT, write_json


def main():
    root = PROJECT / "baselines/wildgs_slam/upstream"
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = PROJECT / "logs/PHASE5" / (stamp + "_wildgs_native_setup")
    out.mkdir(exist_ok=False)
    changes = []
    for path in (root / "src/lib").glob("*.cu"):
        old = path.read_bytes()
        new = b"".join(re.sub(rb"(\b[A-Za-z_]\w*)\.type\(\)", rb"\1.scalar_type()", line) if b"DISPATCH" in line else line for line in old.splitlines(keepends=True))
        if new != old:
            path.write_bytes(new)
            changes.append({"file": path.relative_to(root).as_posix(), "old_sha256": hashlib.sha256(old).hexdigest(), "new_sha256": hashlib.sha256(new).hexdigest(), "reason": "ATen2.7 dispatch scalar-type API; arithmetic unchanged"})
    path = root / "setup.py"
    old = path.read_bytes()
    new = re.sub(rb"^[ \t]*'-gencode=arch=compute_\d+,code=sm_\d+',\r?\n", b"", old, flags=re.M)
    new = new.replace(b"'nvcc': ['-O3',", b"'nvcc': ['-O3', '-gencode=arch=compute_120,code=sm_120',")
    if new != old:
        path.write_bytes(new)
        changes.append({"file": "setup.py", "reason": "Compile same kernels for sm120; remove unsupported legacy NVCC12.8 targets"})
    for relative, target in (("img_feature_extractors.py", 'self.model = torch.hub.load("ywyue/FiT3D", extractor_model).to(device).eval()'),
                             ("metric_depth_estimators.py", 'model = torch.hub.load("yvanyin/metric3d", depth_model, pretrain=True)')):
        path = root / "src/utils/mono_priors" / relative
        text = path.read_text(encoding="utf-8")
        if target in text:
            text = "import os\n" + text
            if relative.startswith("img_"):
                replacement = 'local_repo = os.environ.get("GAMECAM_FIT3D_REPO")\n        self.model = torch.hub.load(local_repo or "ywyue/FiT3D", extractor_model, source="local" if local_repo else "github").to(device).eval()'
            else:
                replacement = 'if os.environ.get("GAMECAM_XFORMERS_DISABLE_FA3") == "1":\n            from xformers.ops.fmha.dispatch import _set_use_fa3\n            _set_use_fa3(False)\n        local_repo = os.environ.get("GAMECAM_METRIC3D_REPO")\n        model = torch.hub.load(local_repo or "yvanyin/metric3d", depth_model, pretrain=True, source="local" if local_repo else "github")'
            path.write_bytes(text.replace(target, replacement).encode("utf-8"))
            changes.append({"file": path.relative_to(root).as_posix(), "reason": "Same official checkpoints from pinned local hub sources; opt-in non-FA3 dispatch after actual sm120 kernel failure"})
    write_json(out / "compatibility_changes.json", changes)
    env = "/home/lsuser/.local/share/gamecam-vo/envs/wildgs_slam"
    conda = "/home/lsuser/.local/share/gamecam-vo/miniforge3"
    shell = f'''#!/bin/bash
set -eo pipefail
source {conda}/etc/profile.d/conda.sh
conda activate {env}
set -u
export MAX_JOBS=1 TORCH_CUDA_ARCH_LIST=12.0 CUDA_HOME="$CONDA_PREFIX"
export CPATH="$CONDA_PREFIX/targets/x86_64-linux/include${{CPATH:+:$CPATH}}"
for include_dir in "$CONDA_PREFIX"/lib/python3.10/site-packages/nvidia/*/include; do
  if [ -d "$include_dir" ]; then export CPATH="$include_dir:$CPATH"; fi
done
cd /mnt/d/aaa/GameCam-VO/baselines/wildgs_slam/upstream
python -m pip install --no-index --no-build-isolation --no-deps --verbose .
python -m pip check
python -c "import torch,sys; print(sys.prefix,torch.__version__,torch.version.cuda); x=torch.arange(16.,device='cuda').reshape(4,4); torch.testing.assert_close((x@x.T).cpu(),x.cpu()@x.cpu().T); print('ACTUAL_CUDA_MATMUL_PASS')"
python -m pip freeze
'''
    script = out / "build.sh"
    script.write_bytes(shell.encode())
    with (out / "build.log").open("w") as log:
        code = subprocess.run(["wsl.exe", "-d", "Ubuntu", "--exec", "/bin/bash", "/mnt/d/aaa/GameCam-VO/" + script.relative_to(PROJECT).as_posix()], stdout=log, stderr=subprocess.STDOUT).returncode
    record = {"status": "WILDGS_BACKEND_BUILT_PENDING_NATIVE_PROBES" if code == 0 else "WILDGS_BACKEND_BUILD_FAILED", "environment": env,
              "directory": str(out), "exit_code": code, "changes": changes, "existing_environments_modified": False,
              "vendor_extension_reuse_requires_source_comparison_and_native_probe": True, "model_inference_executed": False}
    write_json(out / "status.json", record)
    write_json(PROJECT / "reports/PHASE5/wildgs_native_setup.json", record)
    print(json.dumps({k: record[k] for k in ("status", "directory", "exit_code")}))


if __name__ == "__main__":
    main()
