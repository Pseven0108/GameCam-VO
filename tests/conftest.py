"""Enable the EXR codec before any test imports OpenCV."""
import os

os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")
