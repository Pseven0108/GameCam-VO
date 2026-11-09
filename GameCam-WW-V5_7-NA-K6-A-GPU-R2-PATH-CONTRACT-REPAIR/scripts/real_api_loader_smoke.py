"""Actual installed loader APIs, fake pinned bytes, mocked deserializers; no CUDA work."""
import argparse,hashlib,json,os,pathlib,sys,tempfile,traceback
from unittest import mock
from runtime_dependency_pins import RuntimePins,PinError,require

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    output=pathlib.Path(a.output);output.parent.mkdir(parents=True,exist_ok=True);report={'status':'FAIL','real_checkpoint_deserialized':False,'GT_values_read':False,'tests':[]}
    pins=RuntimePins.__new__(RuntimePins);pins.events=[];pins.event_sink=None;pins.gate=None
    try:
        with tempfile.TemporaryDirectory(prefix='k6a-real-api-fake-only-') as temp:
            root=pathlib.Path(temp);weights={}
            for i in range(4):
                path=root/('fake_'+str(i)+('.safetensors' if i==3 else '.pth'));raw=f'FAKE_ONLY_NO_CHECKPOINT_{i}'.encode();path.write_bytes(raw)
                weights[str(i)]=dict(id=str(i),path_linux=str(path),path_windows=str(path),real_linux=str(path),real_windows=str(path),allowed_root_linux=str(root),allowed_root_real_linux=str(root),allowed_root_windows=str(root),allowed_root_real_windows=str(root),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),loader='safetensors.torch.load_file' if i==3 else 'torch.load',url=f'https://approved.invalid/{path.name}')
            pins.weights=weights;pins.spec={'environment':{'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'},'hub_models':{}}
            os.environ.update(pins.spec['environment']);pins.assert_manifest=lambda:None;pins.check_revision=lambda:None
            # This smoke tests real API wrapping. Complete RuntimePins initialization is separately tested by fake-package fixtures and live CPU static checks.
            pins.install_before_import()
            import torch,torch.serialization,safetensors.torch
            pins.assert_hooks(require_torch=True)
            assert not torch.cuda.is_initialized()
            with mock.patch.object(torch.serialization,'_legacy_load',return_value={'fake_deserializer':True}) as legacy:
                for label,fn in [('torch.load',torch.load),('torch.serialization.load',torch.serialization.load)]:
                    result=fn(weights['0']['path_linux'],map_location='cpu',weights_only=False);assert result['fake_deserializer'];report['tests'].append({'api':label,'passed':True,'real_api_called':True,'deserializer':'mocked'})
                result=torch.hub.load_state_dict_from_url(weights['0']['url'],model_dir=str(root),file_name=pathlib.Path(weights['0']['path_linux']).name,weights_only=False,progress=False);assert result['fake_deserializer'];report['tests'].append({'api':'torch.hub.load_state_dict_from_url','passed':True,'cache_hit':True,'deserializer':'mocked'});assert legacy.call_count==3
            class FakeSafeOpen:
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def keys(self):return []
                def get_tensors(self):return {}
            with mock.patch.object(safetensors.torch,'safe_open',return_value=FakeSafeOpen()) as opened:
                assert safetensors.torch.load_file(weights['3']['path_linux'])=={};assert opened.call_count==1;report['tests'].append({'api':'safetensors.torch.load_file','passed':True,'real_api_called':True,'safe_open':'mocked'})
            import huggingface_hub
            assert ('huggingface_hub','hf_hub_download') in pins.gate.bindings
            try:huggingface_hub.snapshot_download('unapproved/fixture')
            except PinError:report['tests'].append({'api':'huggingface_hub.snapshot_download','passed':True,'network_called':False,'rejected_before_original':True})
            else:raise AssertionError('snapshot download was not rejected')
            assert not torch.cuda.is_initialized()
            report.update(status='PASS',torch_version=str(torch.__version__),cuda_initialized=False,gate_bindings=[list(key) for key in pins.gate.bindings],loader_events=len(pins.events),actual_api_passes=len(report['tests']))
    except BaseException as exc:report.update(error=str(exc),traceback=traceback.format_exc())
    finally:
        if pins.gate:pins.gate.close()
    output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('traceback','gate_bindings')}));return 0 if report['status']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
