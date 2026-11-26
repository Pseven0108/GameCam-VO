"""Read the public delivery anonymously, verify hashes/CRC, then remove its local ZIP only."""
import hashlib
import io
import json
from pathlib import Path
import time
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1];PROJECT=ROOT.parents[1]
PUB=PROJECT/'maintenance/GITHUB_TASK008_PUBLICATION_20261126'
R=PROJECT/'reviews/task008-pi3mos-night007-independent-inference-20261126'
receipt=json.loads((PUB/'PUBLICATION_RECEIPT.json').read_text());REPO=receipt['repository'];COMMIT=receipt['commit']

def read(url):
    request=urllib.request.Request(url,headers={'User-Agent':'GameCam-VO-Anonymous-TASK008-Review-Readback'})
    with urllib.request.urlopen(request,timeout=90) as response:return response.read()

def api(path):return json.loads(read('https://api.github.com/repos/'+REPO+path))

repo=api('');assert repo['visibility']=='public' and repo['default_branch']=='codex/research-review-20261124'
release=api('/releases/tags/'+receipt['tag']);assert not release['draft']
tag=api('/git/ref/tags/'+receipt['tag']);assert tag['object']['sha']==COMMIT and tag['object']['type']=='commit'
commit=api('/git/commits/'+COMMIT);assert [r['sha'] for r in commit['parents']]==['3bf7da7bb39192081cefe9898e948784ae6cd5aa']
tree=api('/git/trees/'+commit['tree']['sha']+'?recursive=1');assert not tree['truncated']
items={r['path']:r for r in tree['tree']}
for row in receipt['expanded_files']:
    actual=items[row['path']]
    assert actual['type']=='blob' and actual['sha']==row['sha'] and actual['size']==row['bytes']
prefix='reviews/'+receipt['tag']+'/'
for path in [prefix+'FINAL_REVIEW.md',prefix+'figures/RGB312_FIVE_FRAME_DETAIL.jpg',
             'experiments/task008_pi3mos/scripts/infer_pi3mos_safetensors.py']:
    raw=read('https://raw.githubusercontent.com/'+REPO+'/'+COMMIT+'/'+path)
    row=next(r for r in receipt['expanded_files'] if r['path']==path)
    assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
assets=[a for a in release['assets'] if a['name']==receipt['ZIP']['ZIP_name']];assert len(assets)==1
asset=assets[0];assert asset['digest']=='sha256:'+receipt['ZIP']['ZIP_sha256'] and asset['size']==receipt['ZIP']['ZIP_bytes']
raw=read(asset['browser_download_url']);archive=R/'deliveries'/receipt['ZIP']['ZIP_name']
assert len(raw)==receipt['ZIP']['ZIP_bytes'] and hashlib.sha256(raw).hexdigest()==receipt['ZIP']['ZIP_sha256']
assert archive.read_bytes()==raw
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    assert z.testzip() is None and len(z.namelist())==receipt['ZIP']['ZIP_members']
    rows=json.loads(z.read('FILE_SHA256_MANIFEST.json'))['files']
    assert len(rows)==receipt['ZIP']['internal_SHA256_entries']
    assert {r['path'] for r in rows}==set(z.namelist())-{'FILE_SHA256_MANIFEST.json'}
    for row in rows:
        b=z.read(row['path']);assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256']
        assert b==(R/row['path']).read_bytes()
result={**receipt,'state':'PUBLISHED_AND_ANONYMOUSLY_VERIFIED','anonymous_ZIP_download':True,'CRC':'PASS',
    'internal_SHA256':str(len(rows))+'/'+str(len(rows))+' PASS','expanded_files_verified':len(receipt['expanded_files']),
    'expanded_tree_blob_identities_match':True,'main_report_code_and_real_figure_raw_bytes_verified':True,
    'checked_at_UTC':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
with (PUB/'PUBLICATION_VERIFIED.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
# The user's standing cleanup instruction applies only to this delivered local review archive.
assert archive.parent.resolve()==(R/'deliveries').resolve() and not archive.is_symlink()
assert archive.name=='GAMECAM_TASK008_PI3MOS_NIGHT007_REVIEW.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==receipt['ZIP']['ZIP_sha256']
archive.unlink()
cleanup={'state':'JUST_DELIVERED_LOCAL_REVIEW_ZIP_REMOVED_AFTER_ANONYMOUS_VERIFICATION','path':str(archive),
         'bytes':len(raw),'sha256':receipt['ZIP']['ZIP_sha256'],'expanded_review_preserved':True,
         'raw_float32_predictions_and_remote_originals_preserved':True,'historical_files_deleted':0}
with (PUB/'LOCAL_REVIEW_ZIP_DELETION_RECEIPT.json').open('x',encoding='utf-8') as f:json.dump(cleanup,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in result.items() if k!='expanded_files'},indent=2))
print(json.dumps(cleanup,indent=2))
