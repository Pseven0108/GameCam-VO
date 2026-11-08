"""Execute the original optional-GUI cleanup method in isolation, without CUDA."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parents[1]
source = root / "baselines/pi3mos/upstream/demo.py"
module = ast.parse(source.read_text(encoding="utf-8"))
cls = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "Pi_SAM")
method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "shutdown_gui")
namespace = {}
exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)
try:
    namespace["shutdown_gui"](SimpleNamespace())
except AttributeError as error:
    failure = str(error)
else:
    raise RuntimeError("Expected original headless missing-attribute issue did not occur")
assert namespace["shutdown_gui"](SimpleNamespace(gui_process=None)) is None
record = {"status": "ORIGINAL_HEADLESS_GUI_ATTRIBUTE_FAILURE_REPRODUCED", "original_error": failure,
          "explicit_gui_process_None_cleanup": "passed", "GPU_or_model_inference": False,
          "planned_io_fix": "Owned headless subclass initializes the omitted optional GUI handle to None. Original run/tracking/optimization remain unchanged.",
          "upstream_source_modified": False}
(root / "reports/SOTA/pi3mos_headless_cleanup_probe.json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
print(json.dumps(record))
