"""Frozen R2 RGB-only loader, hard-limited to indices 0..79 for this smoke."""
import hashlib,json
from pathlib import Path
import cv2
import numpy as np
import torch
from src.utils.datasets import RGB_NoPose
from control_common import ControlError,file_sha

INPUT_SHA='5547cdd407e022ba27a8b9af18f1ef4e9471ea58c1e0df96aec38fee180aa537'

class NativeViperRGB(RGB_NoPose):
    def __init__(self,cfg,manifest,out):
        super().__init__(cfg)
        manifest=Path(manifest)
        if file_sha(manifest)!=INPUT_SHA:raise ControlError('Frozen val_007 input manifest changed')
        self.manifest_sha256=INPUT_SHA;self.manifest_path=manifest
        self.doc=json.loads(manifest.read_text());self.frames=self.doc['frames'];self.ids=[f['rgb_id'] for f in self.frames]
        if self.ids!=list(range(1,488)) or self.doc['branch']!='FIXED_K_NATIVE_RESIZE':raise ControlError('Unexpected R2 input branch')
        self.color_paths=[str(manifest.parent/f['file']) for f in self.frames];self.n_img=len(self.ids)
        self.out=Path(out);self.seen=0
    def __getitem__(self,index):
        if type(index) is not int or not 0<=index<80:raise ControlError('RGB beyond 080 is not authorized')
        if index!=self.seen:raise ControlError('Native stream cursor mismatch')
        row=self.frames[index];p=Path(self.color_paths[index])
        expected=row.get('sha256',row.get('rgb_sha256'))
        if expected and file_sha(p)!=expected:raise ControlError('RGB content changed')
        item=super().__getitem__(index);ts,color,depth,pose=item
        if ts!=index or pose is not None or depth is not None or tuple(color.shape)!=(1,3,360,640):raise ControlError('R2 RGB-only input contract mismatch')
        self.seen+=1
        return item
