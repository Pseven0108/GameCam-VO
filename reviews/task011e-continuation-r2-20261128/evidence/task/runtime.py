"""Deferred native runtime. Imported only by an explicitly approved driver.

Reuses frozen TASK011B configuration/helper code; RGB paths and seeds are new.
No GT file is present in the GPU-facing manifest.
"""
import importlib.util,json,os,sys
from pathlib import Path
import numpy as np

TASK=Path(__file__).resolve().parent
FRESH=Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408')
SOURCE=FRESH/'source/DROID-W'
sys.path[:0]=[str(SOURCE),str(TASK)]
spec=importlib.util.spec_from_file_location('task011d_frozen_runtime',TASK.parent/'TASK011B/gpu/runtime.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
old.TASK=TASK;old.SOURCE=SOURCE
sha=old.sha;write=old.write;offline_hub=old.offline_hub

def inputs(window):
    return next(x for x in json.loads((TASK/'configs/GPU_RGB_INPUTS.json').read_text())['windows'] if x['window_id']==window)
old.inputs=inputs
config=old.config
from src.utils.datasets import RGB_NoPose
class Stream(RGB_NoPose):
    def __init__(self,cfg,window):
        super().__init__(cfg);item=inputs(window)
        self.ids=[f['rgb_id'] for f in item['frames']]
        self.color_paths=[str(TASK/f['relative_path']) for f in item['frames']];self.n_img=len(self.ids)
        np.testing.assert_allclose(self.get_intrinsic().cpu().numpy(),item['K_640x360'],atol=5e-5,rtol=0)
        for path,r in zip(self.color_paths,item['frames']):
            if Path(path).stat().st_size!=r['bytes'] or sha(path)!=r['sha256']:raise RuntimeError('Original JPEG identity mismatch')
def stream_class():return Stream
