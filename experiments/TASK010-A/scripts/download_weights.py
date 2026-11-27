"""Fetch official candidate weights to D:, with bounded per-file downloads."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import time
import requests
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from bootstrap import TASK, EXT, get, dump


def fetch(item):
    name,url=item
    dest=EXT/'weights'/name;dest.parent.mkdir(parents=True,exist_ok=True)
    record={'name':name,'official_url':url,'path':str(dest)}
    try:
        if not dest.exists():
            session=requests.Session()
            if name=='gmos_s.pth':
                # gdown handles Google's public-file confirmation page; no account token.
                import gdown
                result=gdown.download(id='1SAyc4maUcpZNgpHjkKN9jxyrHkVp2JBq',output=str(dest)+'.part',quiet=False)
                if not result:raise RuntimeError('Official Google Drive weight inaccessible')
                Path(result).rename(dest)
            else:
                with session.get(url,stream=True,timeout=(20,60)) as r:
                    r.raise_for_status()
                    if 'text/html' in r.headers.get('Content-Type',''):raise RuntimeError('HTML instead of model')
                    total=int(r.headers.get('Content-Length','0'))
                    if total>7*1024**3:raise RuntimeError('Checkpoint exceeds per-file bound')
                    count=0
                    with dest.with_suffix(dest.suffix+'.part').open('xb') as f:
                        for chunk in r.iter_content(8*1024**2):
                            count+=len(chunk)
                            if count>7*1024**3:raise RuntimeError('Checkpoint download exceeded bound')
                            f.write(chunk)
                    if total and total!=count:raise RuntimeError('Incomplete HTTP body')
                    dest.with_suffix(dest.suffix+'.part').rename(dest)
        h=hashlib.sha256()
        with dest.open('rb') as f:
            for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
        record.update(status='DOWNLOADED',bytes=dest.stat().st_size,sha256=h.hexdigest())
    except Exception as e:record.update(status='FAILED',error=str(e))
    print(json.dumps(record),flush=True)
    dump(TASK/'09_reproducibility'/('WEIGHT_'+name+'.json'),record)
    return record


if __name__=='__main__':
    items=[('pi3.safetensors','https://huggingface.co/yyfz233/Pi3/resolve/main/model.safetensors'),
           ('sam2.1_hiera_large.pt','https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt'),
           ('gmos_s.pth','https://drive.google.com/file/d/1SAyc4maUcpZNgpHjkKN9jxyrHkVp2JBq/view'),
           ('geomotion_cvpr.pth','https://huggingface.co/xingyang1/GeoMotion/resolve/main/best_model.pth'),
           ('raft_large.pth','https://download.pytorch.org/models/raft_large_C_T_SKHT_V2-ff5fadd5.pth')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:result=list(pool.map(fetch,items))
    dump(TASK/'09_reproducibility/WEIGHT_DOWNLOADS.json',result)
