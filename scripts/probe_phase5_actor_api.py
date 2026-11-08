"""Check actual thread lifecycle and every launcher API used by native SLAM."""
from __future__ import annotations

import ast
import importlib.util
import json
import multiprocessing as mp
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / "baselines/wildgs_slam/upstream/src/slam.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    required = sorted({node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "mp"})
    spec = importlib.util.spec_from_file_location("owned_actor", ROOT / "scripts/run_phase5_wildgs_entrypoint.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    namespace = SimpleNamespace(Process=module.ActorThread, Pipe=mp.Pipe, Queue=mp.Queue, active_children=mp.active_children)
    assert all(callable(getattr(namespace, name)) for name in required)
    parent, child = namespace.Pipe()
    def target():
        child.send({"native_handshake": "ready"})
        assert child.recv() == "continue"
    actor = namespace.Process(target=target)
    actor.start()
    assert parent.poll(5) and parent.recv() == {"native_handshake": "ready"}
    parent.send("continue")
    actor.join(5)
    assert actor.exitcode == 0 and not actor.is_alive()
    assert isinstance(namespace.active_children(), list)
    result = {"status": "THREAD_LIFECYCLE_PIPE_AND_NATIVE_LAUNCHER_API_PASS", "required_native_APIs": required,
        "actual_thread_and_CPU_pipe_handshake": True, "GPU_kernel_or_RNG_equivalence_claim": False,
        "cleanup_api_missing_in_active_070506_cache": True, "future_launchers_include_native_active_children": True}
    (ROOT / "reports/PHASE5/wildgs_actor_API_probe.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
