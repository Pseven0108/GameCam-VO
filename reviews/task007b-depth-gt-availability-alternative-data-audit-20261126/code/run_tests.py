import io
import json
import os
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parents[1]
assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1"
stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.discover(str(root / "tests")))
(root / "logs").mkdir(exist_ok=True)
with (root / "logs/CPU_UNIT_TESTS.txt").open("x", encoding="utf-8") as f: f.write(stream.getvalue())
report = {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
          "status": "PASS" if result.wasSuccessful() else "FAIL", "device": "CPU", "torch_imported": "torch" in sys.modules,
          "scope": "Content-classifier contracts and synthetic unit-invariance/split properties only; no GT accuracy or statistical calibration result",
          "python_executable": sys.executable}
with (root / "tests/CPU_TEST_REPORT.json").open("x", encoding="utf-8") as f: json.dump(report, f, indent=2); f.write("\n")
print(json.dumps(report, indent=2))
if not result.wasSuccessful(): raise SystemExit(1)
