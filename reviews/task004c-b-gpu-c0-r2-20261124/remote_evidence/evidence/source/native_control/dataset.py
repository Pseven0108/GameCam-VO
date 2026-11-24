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
        # Reject label sources before the parent loader can read them.
        if self.depth_paths is not None or self.poses is not None:
            raise ControlError('RGB-only stream contains an unexpected label source')
        row=self.frames[index];p=Path(self.color_paths[index])
        if type(row.get('rgb_id')) is not int or row['rgb_id']!=index+1:
            raise ControlError('RGB frame ID does not match the frozen cursor')
        expected=row.get('sha256',row.get('rgb_sha256'))
        if expected and file_sha(p)!=expected:raise ControlError('RGB content changed')
        item=super().__getitem__(index);ts,color,depth,pose=item
        if (type(ts) is not int or ts!=index or pose is not None
                or not isinstance(color,torch.Tensor) or tuple(color.shape)!=(1,3,360,640)):
            raise ControlError('R2 RGB-only input contract mismatch')
        # BaseDataset uses this exact zero Tensor to represent absent depth.
        # Keep the original tuple and reject None, labels, NaN/Inf and other layouts.
        if (not isinstance(depth,torch.Tensor) or depth.dtype!=torch.float32
                or depth.device.type!='cpu' or tuple(depth.shape)!=tuple(color.shape[-2:])
                or depth.layout!=torch.strided or bool(torch.count_nonzero(depth))):
            raise ControlError('Invalid RGB-only zero-depth placeholder')
        self.seen+=1
        return item
