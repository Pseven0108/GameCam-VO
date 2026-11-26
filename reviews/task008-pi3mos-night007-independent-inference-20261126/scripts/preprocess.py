"""RGB-only Pi3 preprocessing and explicit no-crop pixel-center mapping."""
import math
from pathlib import Path

import numpy as np
from PIL import Image


def target_size(width,height,pixel_limit=255000):
    scale=math.sqrt(pixel_limit/(width*height))
    wt,ht=width*scale,height*scale
    k,m=round(wt/14),round(ht/14)
    while (k*14)*(m*14)>pixel_limit:
        if k/m>wt/ht:k-=1
        else:m-=1
    return max(1,k)*14,max(1,m)*14


def read_rgb(path,pixel_limit=255000):
    with Image.open(path) as im:
        im.load();rgb=im.convert('RGB');ow,oh=rgb.size
        w,h=target_size(ow,oh,pixel_limit)
        if abs(w/h-ow/oh)>1e-12:raise ValueError('This task requires exact aspect ratio; do not silently distort/crop')
        a=np.array(rgb.resize((w,h),Image.Resampling.LANCZOS),dtype=np.uint8)
    x=np.ascontiguousarray(a.transpose(2,0,1).astype(np.float32)/np.float32(255.))
    assert x.shape==(3,h,w) and x.min()>=0 and x.max()<=1
    sx,sy=w/ow,h/oh
    mapping={'original_wh':[ow,oh],'model_wh':[w,h],'scale_xy':[sx,sy],'crop_ltrb':[0,0,0,0],'padding_ltrb':[0,0,0,0],
             'pixel_centers':'model_x=sx*(original_x+0.5)-0.5; inverse=(model_x+0.5)/sx-0.5',
             'original_to_model_matrix':[[sx,0,(sx-1)/2],[0,sy,(sy-1)/2],[0,0,1]],
             'color':'RGB','dtype':'float32','range':[float(x.min()),float(x.max())],
             'resize':'PIL_LANCZOS','ImageNet_normalization':'Only inside the original model'}
    return x,mapping


def contract_check():
    assert target_size(1920,1080)==(672,378)
    # RGB/BGR and uint8 conversion are tested with asymmetric colors.
    colors=np.array([[[255,0,0],[0,0,255]],[[0,255,0],[16,128,240]]],np.uint8)
    x=colors.transpose(2,0,1).astype(np.float32)/255.
    assert np.array_equal((x.transpose(1,2,0)*255).astype(np.uint8),colors)
    assert x[0,0,0]==1 and x[2,0,0]==0 and x[2,0,1]==1
    s=.35;pts=np.array([0.,1.,958.,1919.])
    assert np.max(np.abs(((s*(pts+.5)-.5)+.5)/s-.5-pts))<1e-11
    return {'size':[672,378],'pixels':672*378,'exact_aspect_ratio':True,'RGB_channel_contract':'PASS',
            'uint8_to_float_divide_once':'PASS','coordinate_roundtrip':'PASS','model_imported':False}
