"""CPU check of preprocessing against original standalone RGB reader."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image
import torch

from preprocess import contract_check,read_rgb

p=argparse.ArgumentParser();p.add_argument('--config',required=True);a=p.parse_args()
c=json.loads(Path(a.config).read_text());w=Path(c['remote_output']);src=Path(c['model_source_outside_project'])
assert subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()==c['source_commit']
sys.path.insert(0,str(src))
from pi3.utils.basic import load_images_as_tensor,preprocess_tensor_for_pi3
fixtures=w/'preprocess_contract_fixture';fixtures.mkdir()
colors=np.zeros((1080,1920,3),np.uint8);colors[:,:640]=[255,0,0];colors[:,640:1280]=[0,255,0];colors[:,1280:]=[0,0,255]
fp=fixtures/'synthetic_color_channels.png';Image.fromarray(colors).save(fp)
ours,m=read_rgb(fp);official=load_images_as_tensor(str(fixtures))[0].numpy()
assert np.array_equal(ours,official),'Independent RGB preprocessing differs from the documented RGB reader'
assert ours[0,100,100]>0.99 and ours[2,100,570]>0.99
fixture_correct=torch.from_numpy(colors.transpose(2,0,1).astype(np.float32)/255.)
good=preprocess_tensor_for_pi3(fixture_correct).numpy()
assert np.array_equal(good,official)
fixture_uint8_BGR=torch.from_numpy(colors[...,::-1].copy().transpose(2,0,1))
bad=preprocess_tensor_for_pi3(fixture_uint8_BGR).numpy()
diff=float(np.abs(bad-official).mean())
assert diff>0.1
record={'CPU_contracts':contract_check(),'independent_vs_official_RGB_reader_bitwise_equal':True,
        'correct_domain_tensor_helper_equal':True,'synthetic_uint8_BGR_tensor_helper_MAD':diff,
        'scope':'CPU synthetic color contract; demonstrates wrong-domain sensitivity, not a claim that every upstream user path is wrong',
        'preprocess_mapping':m,'torch':torch.__version__,'CUDA_build':torch.version.cuda,
        'GPU_initialized':torch.cuda.is_initialized(),'model_created_or_weights_loaded':False,
        'model_forward_expected_dynamic_shape':'[B,N,1,H,W,1], sigmoid output',
        'model_forward_expected_conf_shape':'[B,N,H,W,1], sigmoid output'}
with (w/'CPU_PREPROCESS_CONTRACT.json').open('x',encoding='utf-8') as f:json.dump(record,f,indent=2);f.write('\n')
print(json.dumps(record,indent=2))
