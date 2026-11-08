from __future__ import annotations
import _bootstrap
import importlib.metadata
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import av
import cv2
import psutil

from gamecam_vo.common import PROJECT, utc_now, write_json


def command(args):
    try:
        value = subprocess.run(args, capture_output=True, timeout=20)
        def decode(raw):
            return raw.decode("utf-16-le" if b"\x00" in raw else "utf-8", errors="replace").strip()
        return {"exit_code": value.returncode, "stdout": decode(value.stdout), "stderr": decode(value.stderr)}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}


def main():
    memory = psutil.virtual_memory()
    torch = {"installed": importlib.util.find_spec("torch") is not None, "version": None,
             "cuda_build": None, "cuda_available": None}
    if torch["installed"]:
        try:
            import torch as module
            torch.update(version=module.__version__, cuda_build=module.version.cuda,
                         cuda_available=module.cuda.is_available())
        except Exception as exc:
            torch["import_error"] = f"{type(exc).__name__}: {exc}"
    packages = {}
    for name in ("numpy", "scipy", "opencv-python-headless", "matplotlib", "PyYAML", "psutil", "av", "pytest"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    drives = {}
    for drive in ("C:/", "D:/"):
        if Path(drive).exists():
            value = shutil.disk_usage(drive)
            drives[drive] = {"total_bytes": value.total, "free_bytes": value.free, "used_bytes": value.used}
    windows = command(["powershell.exe", "-NoProfile", "-Command",
                       "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); "
                       "@{os=(Get-CimInstance Win32_OperatingSystem).Caption;"
                       "cpu=(Get-CimInstance Win32_Processor).Name} | ConvertTo-Json -Compress"])
    try:
        windows_hardware = json.loads(windows["stdout"]) if windows.get("exit_code") == 0 else {}
    except (ValueError, KeyError):
        windows_hardware = {}
    result = {"created_utc": utc_now(), "os": windows_hardware.get("os", platform.platform()),
              "python_platform": platform.platform(), "machine": platform.machine(),
              "python": sys.version, "python_executable": sys.executable, "environment": "gamecam-vo",
              "cpu": windows_hardware.get("cpu", platform.processor()), "physical_cores": psutil.cpu_count(logical=False),
              "logical_cores": psutil.cpu_count(), "memory_total_bytes": memory.total,
              "memory_available_bytes": memory.available, "disk": drives, "packages": packages,
              "opencv": cv2.__version__, "pyav": av.__version__, "pytorch": torch,
              "nvidia_smi": command(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"]),
              "cuda_toolkit": command(["nvcc", "--version"]), "cuda_driver": command(["nvidia-smi"]),
              "cmake_on_windows": shutil.which("cmake"), "wsl": command(["wsl", "--list", "--quiet"]),
              "notes": ["E0 and E1-A run on CPU without PyTorch.",
                        "CUDA toolkit, driver-supported CUDA, and a PyTorch CUDA build are distinct quantities.",
                        "No model weights are installed or downloaded."]}
    write_json(PROJECT / "reports" / "E0_environment_report.json", result)
    lines = ["# E0 运行环境报告", "", "采集时间（UTC）：" + result["created_utc"], "",
             "- OS: " + result["os"], "- Python: " + sys.version.splitlines()[0],
             "- Environment: gamecam-vo", "- CPU: " + result["cpu"],
             f"- CPU cores: {result['physical_cores']} physical / {result['logical_cores']} logical",
             f"- RAM: {memory.total / 1024**3:.2f} GiB; available at capture: {memory.available / 1024**3:.2f} GiB",
             "- GPU / VRAM / driver: " + result["nvidia_smi"].get("stdout", str(result["nvidia_smi"])),
             "- OpenCV: " + cv2.__version__, "- PyAV: " + av.__version__,
             "- PyTorch: " + ("not installed (E0/E1-A do not require it)" if not torch["installed"] else str(torch)),
             "- CUDA toolkit: " + result["cuda_toolkit"].get("stdout", str(result["cuda_toolkit"])).replace("\n", " / "),
             "", "磁盘空间："]
    lines += [f"- {name}: free {info['free_bytes'] / 1024**3:.2f} GiB / total {info['total_bytes'] / 1024**3:.2f} GiB"
              for name, info in drives.items()]
    lines += ["", "依赖版本：", "", *[f"- {name}: {version}" for name, version in packages.items()],
              "", "完整诊断见同名 JSON；本项目环境保持独立，未修改 base 或其他研究环境。",
              "未安装学习模型，不把驱动支持的 CUDA 版本视为已验证的 PyTorch GPU 环境。"]
    (PROJECT / "reports" / "E0_environment_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(PROJECT / "reports" / "E0_environment_report.md"),
                      "python": platform.python_version(), "opencv": cv2.__version__, "pytorch": torch}, ensure_ascii=False))


if __name__ == "__main__":
    main()
