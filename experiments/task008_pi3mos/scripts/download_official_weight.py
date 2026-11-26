"""Fetch only the official Pi3MOS weight into an external cache, no model load."""
import hashlib
import json
from pathlib import Path
import time

import gdown

ROOT=Path(r'D:\aaa\external_models\pi3mos_task008_weights')
ROOT.mkdir(exist_ok=False)
target=ROOT/'pi3mos_official.pth'
ID='145bC76pMHikhdTGkqDK0t9Ta0R7tw51v'
receipt={'official_file_id':ID,'official_URL':'https://drive.google.com/file/d/'+ID+'/view',
         'weight_source':'Pinned official Pi3MOS-SLAM README','model_loaded':False,'stage':'DOWNLOADING'}
state=ROOT/'DOWNLOAD_STATE.json';state.write_text(json.dumps(receipt,indent=2)+'\n')
start=time.perf_counter()
try:
    result=gdown.download(id=ID,output=str(target),quiet=True,use_cookies=False,resume=False)
    assert result and target.is_file() and target.stat().st_size>100_000_000,'No usable model weight was downloaded'
    h=hashlib.sha256()
    with target.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    receipt.update(stage='COMPLETE',local_path=str(target),bytes=target.stat().st_size,sha256=h.hexdigest(),elapsed_seconds=time.perf_counter()-start,
                   scope='Download identity only; strict model loading happens later on3090')
    state.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
except Exception as e:
    receipt.update(stage='DOWNLOAD_FAILED',error_type=type(e).__name__,elapsed_seconds=time.perf_counter()-start)
    state.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2));raise
