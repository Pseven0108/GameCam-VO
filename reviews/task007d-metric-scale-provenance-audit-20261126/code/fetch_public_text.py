"""Fetch one bounded official text/JSON resource, never archives or weights."""
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
ALLOWED={'huggingface.co','arxiv.org','export.arxiv.org','openreview.net','api.openreview.net','api2.openreview.net','yangzhou24.github.io','raw.githubusercontent.com','api.github.com','github.com'}


def main():
    url,name=sys.argv[1:3]
    parsed=urllib.parse.urlparse(url)
    assert parsed.scheme=='https' and parsed.hostname in ALLOWED
    assert not any(s in parsed.path.lower() for s in ['.tar','.zip','.pt','.pth','.ckpt','.safetensors','.png','.jpg','.mp4','.bin'])
    out=ROOT/name
    assert out.resolve().is_relative_to(ROOT.resolve())
    out.parent.mkdir(parents=True,exist_ok=True)
    assert not out.exists()
    request=urllib.request.Request(url,headers={'User-Agent':'GameCam-VO-TASK007D-Source-Provenance-Audit','Accept-Encoding':'identity'})
    with urllib.request.urlopen(request,timeout=45) as r:
        b=r.read(4*1024*1024+1)
        assert len(b)<=4*1024*1024,'Text resource exceeds4MiB; stop'
        b.decode('utf-8')
        record={'url':url,'status':r.status,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),
                'content_type':r.headers.get('Content-Type'),'ETag':r.headers.get('ETag'),
                'Link':r.headers.get('Link'),'fetched_at_UTC':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                'scope':'Public text/code/metadata only; no raw RGB/depth/archives/models'}
    out.write_bytes(b)
    with out.with_name(out.name+'.receipt.json').open('x',encoding='utf-8') as f:json.dump(record,f,indent=2);f.write('\n')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
