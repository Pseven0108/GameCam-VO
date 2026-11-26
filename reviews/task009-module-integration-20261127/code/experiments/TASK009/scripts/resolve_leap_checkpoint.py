"""Resolve only the official LEAP model; never download the sample dataset."""
import json
from pathlib import Path
import gdown

ROOT=Path(__file__).resolve().parents[3]
output=ROOT/'experiments/TASK009/intake/leap_checkpoint_resolution.json'
try:
    files=gdown.download_folder(id='1muTSIpAvm61YrSZJhOrybcvd34BZ3wK7',skip_download=True,quiet=True,timeout=(10,40))
    rows=[dict(id=x.id,path=str(x.path)) for x in files]
    chosen=[x for x in rows if Path(x['path']).name=='leap_kernel.pth']
    output.write_text(json.dumps({'status':'RESOLVED' if len(chosen)==1 else 'UNRESOLVED','files':rows,'checkpoint':chosen},indent=2))
    print(json.dumps(chosen))
except Exception as e:
    output.write_text(json.dumps({'status':'ACCESS_FAILED','error':str(e)},indent=2))
    raise
