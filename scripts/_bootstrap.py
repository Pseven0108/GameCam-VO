"""Allow the documented 'python scripts/...' commands from an uninstalled checkout."""
import sys
import os
from pathlib import Path

os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
