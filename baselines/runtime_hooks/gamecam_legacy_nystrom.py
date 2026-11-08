"""Load the unchanged, SHA-verified xFormers0.0.23 Python Nyström component."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


source = Path(__file__).resolve().parents[1] / "ba_track/prior_sources/xformers_0_0_23/nystrom.py"
if hashlib.sha256(source.read_bytes()).hexdigest() != "65ae6f786226b2ff63fab9c0d1f00777ad531b23677dd63a2353b800a5a08ded":
    raise ImportError("The original verified xFormers0.0.23 Nyström source is absent or changed")
name = "xformers.components.attention._gamecam_legacy_nystrom_0_0_23"
if name not in sys.modules:
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
NystromAttention = sys.modules[name].NystromAttention
