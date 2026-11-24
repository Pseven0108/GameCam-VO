"""Resolve canonical evidence without relocating or overwriting historical files."""
import pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
EXTERNAL_ROOT=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125')
def stage_dir(mode,namespace='R3_OFFLINE'):
    local=ROOT/'raw_evidence'/namespace/'attempts'/mode
    external=EXTERNAL_ROOT/'raw_evidence'/namespace/'attempts'/mode
    return local if local.exists() or not external.exists() else external
