import io,tarfile,base64,json,pathlib
from transport import ROOT,rpc
release=ROOT/'release'
content=io.BytesIO()
with tarfile.open(fileobj=content,mode='w:gz') as t:
    for p in release.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:t.add(p,arcname=p.relative_to(release).as_posix())
auth=json.loads((release/'AUTHORIZATION.json').read_text())
payload=dict(root=auth['remote_root'],refs=json.loads((release/'REFERENCE_FILES.json').read_text()),source=json.loads((release/'SOURCE_PINS.json').read_text()),release_tar_b64=base64.b64encode(content.getvalue()).decode())
result=rpc((ROOT/'tools/remote_prepare.py').read_text(),'PREPARE',300,payload)
(ROOT/'evidence/PREFLIGHT.json').write_bytes(result)
