"""Cooperative Rerun writer pause; acknowledgement occurs after CUDA sync."""
import time
from contextlib import contextmanager
from control_common import ControlError


class WriterBarrier:
    def __init__(self,context):
        self.request=context.Event();self.acknowledged=context.Event();self.viewer_ready=context.Event()

    def pause_point(self,synchronize):
        self.viewer_ready.set()
        if self.request.is_set():
            synchronize()
            self.acknowledged.set()
            while self.request.is_set():time.sleep(.005)
            self.acknowledged.clear()

    @contextmanager
    def quiesce(self,timeout=15):
        if not self.viewer_ready.wait(timeout):raise ControlError('Native Rerun writer not ready')
        self.request.set()
        if not self.acknowledged.wait(timeout):
            self.request.clear();raise ControlError('Native Rerun writer failed to quiesce')
        try:yield
        finally:self.request.clear()
