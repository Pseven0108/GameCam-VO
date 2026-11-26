"""Preserve attempt01 and create a format-correct adapter without changing model bytes."""
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
old=(root/'scripts/infer_pi3mos.py').read_text('utf-8')
before="""        if checkpoint.suffix=='.safetensors':
            from safetensors.torch import load_file
            weight=load_file(str(checkpoint),device='cpu')
        else:weight=torch.load(str(checkpoint),map_location='cpu',weights_only=True)
"""
after="""        # Official download has a safetensors header despite our initial .pth name.
        # Validate the binary format; do not fall back to unrestricted pickle.
        import struct
        with checkpoint.open('rb') as sf:
            header_bytes=struct.unpack('<Q',sf.read(8))[0]
            assert 0<header_bytes<4*1024**2
            header=json.loads(sf.read(header_bytes))
        assert len(header)==1276 and all('data_offsets' in x for x in header.values())
        assert max(x['data_offsets'][1] for x in header.values())==checkpoint.stat().st_size-header_bytes-8
        from safetensors.torch import load_file
        weight=load_file(str(checkpoint),device='cpu')
"""
assert before in old
new=old.replace(before,after).replace("'strict':True,'missing_keys'","'binary_format':'safetensors','header_tensor_count':len(header),'strict':True,'missing_keys'")
p=root/'scripts/infer_pi3mos_safetensors.py'
with p.open('x',encoding='utf-8') as f:f.write(new)
c=json.loads((root/'configs/night007.json').read_text())
c['remote_output']='/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R2_FORMAT_VERIFIED'
c['weight_reader']='safetensors.torch.load_file, verified binary header; strict=True'
c['first_loader_attempt']='Preserved R1: .pth filename incorrectly selected torch.load; no GPU forward occurred'
with (root/'configs/night007_safetensors.json').open('x',encoding='utf-8') as f:json.dump(c,f,indent=2);f.write('\n')
with (root/'logs/WEIGHT_FORMAT_CORRECTION.json').open('x',encoding='utf-8') as f:json.dump({
    'initial_adapter_sha256':hashlib.sha256(old.encode()).hexdigest(),
    'corrected_adapter_sha256':hashlib.sha256(new.encode()).hexdigest(),
    'model_bytes_changed':False,'algorithm_or_preprocess_changed':False,'initial_GPU_forwards':0,
    'header_bytes':129656,'tensor_count':1276,'unrestricted_pickle_used':False,
    'initial_attempt_preserved':True},f,indent=2);f.write('\n')
print('Created separate safetensors reader and config; initial adapter/run retained')
