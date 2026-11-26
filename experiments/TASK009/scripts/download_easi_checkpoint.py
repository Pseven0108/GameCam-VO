"""Download just the official DUSt3R checkpoint, keeping all bytes on D:."""
import hashlib
import json
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[3]
URL='https://download.europe.naverlabs.com/ComputerVision/DUSt3R/DUSt3R_ViTLarge_BaseDecoder_512_dpt.pth'
target=ROOT/'external/weights/DUSt3R_ViTLarge_BaseDecoder_512_dpt.pth'
receipt=ROOT/'experiments/TASK009/intake/easi_weight_receipt.json'
if target.exists():raise RuntimeError('Existing file is preserved')
part=target.with_suffix('.pth.part')
if part.exists():raise RuntimeError('Existing partial download is preserved')
try:
    with requests.get(URL,stream=True,timeout=(15,45)) as response:
        response.raise_for_status()
        expected=int(response.headers.get('Content-Length',0))
        if expected>3*1024**3:raise RuntimeError('Unexpected checkpoint size over bounded 3GiB')
        h=hashlib.sha256();total=0
        with part.open('xb') as f:
            for chunk in response.iter_content(2**20):
                if chunk:
                    total+=len(chunk)
                    if total>3*1024**3:raise RuntimeError('Checkpoint exceeds bounded transfer')
                    h.update(chunk);f.write(chunk)
        if expected and expected!=total:raise RuntimeError('Incomplete download')
        part.rename(target)
        result={'status':'DOWNLOADED','source':URL,'bytes':total,'sha256':h.hexdigest(),
                'license_scope':'External research-only dependency; never included in core distribution'}
except Exception as error:
    receipt.write_text(json.dumps({'status':'DOWNLOAD_FAILED','error':str(error),'source':URL},indent=2));raise
receipt.write_text(json.dumps(result,indent=2));print(json.dumps(result))
