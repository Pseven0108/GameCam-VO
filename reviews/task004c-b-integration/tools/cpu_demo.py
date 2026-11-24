"""Preserve an inspectable CPU fixture; this is explicitly NOT a real C0."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import hashlib,json,pathlib,random,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import torch
torch.cuda._lazy_init=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('CPU fixture: CUDA forbidden'))
from native_control.snapshot import save_state,load_state
from native_control.cpu_fixtures import fixture_bundle
from control_common import file_sha
def main():
    label=sys.argv[1] if len(sys.argv)>1 else ''
    if label and not label.isidentifier():raise ValueError('Invalid CPU demo label')
    out=ROOT/'artifacts'/('CPU_INSPECTABLE_FIXTURE'+('_'+label if label else ''));out.mkdir(exist_ok=False)
    random.seed(43);np.random.seed(43);torch.random.default_generator.manual_seed(43)
    before=fixture_bundle();m=save_state(before,out/'SNAPSHOT',provenance={'artifact_kind':'CPU_NATIVE_INTERFACE_FIXTURE','not_a_native_C0':True,'seed':43})
    after,restored=load_state(out/'SNAPSHOT',expected_sha=m['state_sha256'])
    receipt={'scope':'CPU_ONLY_SYNTHETIC_FIXTURE_NOT_NATIVE_C0','tensor_nodes':sum(x['kind']=='tensor' for x in m['nodes'].values()),
             'state_sha256':m['state_sha256'],'alias_preserved':after['tracker'].view is after['tracker'].same_view,
             'forward_matches':bool(torch.equal(before['tracker'].model(before['input']),after['tracker'].model(after['input']))),
             'cuda_initialized':torch.cuda.is_initialized(),'real_model_weights_loaded':False}
    (out/'CPU_FIXTURE_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
if __name__=='__main__':main()
