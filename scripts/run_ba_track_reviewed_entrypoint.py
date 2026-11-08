"""Run an unchanged reviewed upstream entry point with explicit compatibility paths."""
from __future__ import annotations

from pathlib import Path
import os
import runpy
import sys


ROOT = Path("/mnt/d/aaa/GameCam-VO")
UPSTREAM = ROOT / "baselines/ba_track/upstream"
allowed = {"Depth-Anything/run_videos_v2.py", "UniDepth/scripts/demo_mega-sam.py", "main/mono_depth/get_mono_depth.py", "main/run_batrack.py", "main/global_refine/run_global_refine.py"}
relative = sys.argv[1]
if relative not in allowed:
    raise ValueError("Only the reviewed BA-Track Demo entry points are allowed")
sys.path[:0] = [str(UPSTREAM), str(UPSTREAM / "main"), str(UPSTREAM / "UniDepth"), str(UPSTREAM / "Depth-Anything"), str(ROOT / "baselines/runtime_hooks")]
sys.path.insert(0, str((UPSTREAM / relative).parent))
from xformers.ops.fmha.dispatch import _set_use_fa3
_set_use_fa3(False)
if os.environ.get("MPLBACKEND"):
    # evo explicitly applies its own saved Qt default during plot import.
    # Change the in-process setting only; no user settings file is written.
    from evo.tools.settings import SETTINGS
    SETTINGS.plot_backend = os.environ["MPLBACKEND"]
if relative == "main/run_batrack.py" and os.environ.get("GAMECAM_BA_MOTION_TRACE_DIR"):
    from ba_track_observer import install_observer
    install_observer(os.environ["GAMECAM_BA_MOTION_TRACE_DIR"])
if relative == "main/global_refine/run_global_refine.py" and os.environ.get("GAMECAM_BA_REFINE_TRACE_DIR"):
    from ba_track_refine_trace import install_refine_trace
    install_refine_trace(os.environ["GAMECAM_BA_REFINE_TRACE_DIR"])
if relative in ("main/run_batrack.py", "main/global_refine/run_global_refine.py") and os.environ.get("GAMECAM_BA_RESULT_PICKLE_LOG"):
    from ba_track_result_pickle import install_result_pickle
    install_result_pickle(os.environ["GAMECAM_BA_RESULT_PICKLE_LOG"])
sys.argv = [str(UPSTREAM / relative), *sys.argv[2:]]
runpy.run_path(str(UPSTREAM / relative), run_name="__main__")
