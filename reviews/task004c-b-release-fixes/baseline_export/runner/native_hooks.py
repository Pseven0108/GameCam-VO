"""Opt-in hook API, not installed into frozen DROID-W.

Actual native resume/call-site integration remains unverified. Synthetic tests
exercise this API and never prove a live DROID schedule can cross D branches.
"""
from control_common import ControlError
class ControlHooks:
    def __init__(self,mode,recorder=None,replayer=None):
        if mode not in ('record','replay'):raise ControlError('Bad hook mode')
        self.mode=mode;self.recorder=recorder;self.replayer=replayer;self.pending=None;self.failed=False
    def before(self,kind,frame_id,proposed,context):
        if self.failed or self.pending is not None:
            self.failed=True
            raise ControlError('Stopped hook or unpaired nested primitive')
        self.pending=(kind,frame_id,context)
        return proposed if self.mode=='record' else self.replayer.select(kind,frame_id,context)
    def after(self,actual_payload,context_after):
        if self.failed or self.pending is None:raise ControlError('Stopped/unpaired event completion')
        kind,frame,before=self.pending
        if self.mode=='record':self.recorder.append(frame,kind,actual_payload,before,context_after)
        else:
            if actual_payload!=self.replayer.pending['payload']:
                self.failed=True;self.replayer.failed=True
                raise ControlError('Native operation did not apply scheduled controls')
            self.replayer.confirm(context_after)
        self.pending=None

def common_init_depth_regularization(phase,native_default):
    if phase in ('frontend_init_neighborhood','frontend_init_proximity','frontend_init_second'):return False
    return native_default
