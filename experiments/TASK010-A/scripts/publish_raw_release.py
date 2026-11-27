"""Publish only this task's new evidence assets; credentials stay in memory.

The connector cannot stream local binary archives. The repository's existing
authorized Git Credential Manager is used, never a token in arguments/files.
"""
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
PRIVATE=TASK/'private/publication';TAG='task010a-research-20261127'
REPO='Pseven0108/GameCam-VO';API='https://api.github.com/repos/'+REPO


def api(method,path,token=None,value=None):
    headers={'User-Agent':'GameCam-VO-Evidence-Delivery','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}
    if token:headers['Authorization']='Bearer '+token
    data=None if value is None else json.dumps(value).encode()
    if data:headers['Content-Type']='application/json'
    try:
        with urlopen(Request(API+path,data=data,headers=headers,method=method),timeout=90) as r:return json.load(r)
    except HTTPError as e:
        # Do not print access-bearing request headers, redirects or response dumps.
        raise RuntimeError(f'GitHub API {method} {path} returned HTTP{e.code}') from None


def credentials():
    env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never')
    r=subprocess.run(['git','-c','credential.interactive=never','credential','fill'],
        input='protocol=https\nhost=github.com\n\n',text=True,capture_output=True,cwd=ROOT,env=env)
    if r.returncode:raise RuntimeError('Existing Git Credential Manager authorization is unavailable; no credential printed')
    fields=dict(line.split('=',1) for line in r.stdout.splitlines() if '=' in line)
    token=fields.get('password')
    if not token:raise RuntimeError('No existing credential available; no secret requested or logged')
    return token


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()


def upload(asset,release,token):
    path=Path(asset['source']);actual=sha(path)
    if actual!=asset['sha256']:raise RuntimeError('Local archive changed before upload')
    address=urlsplit(release['upload_url'].split('{')[0]+'?'+urlencode({'name':path.name}))
    if address.hostname!='uploads.github.com':raise RuntimeError('Unexpected upload host')
    conn=http.client.HTTPSConnection(address.hostname,timeout=180)
    try:
        conn.putrequest('POST',address.path+'?'+address.query)
        for key,value in {'Authorization':'Bearer '+token,'User-Agent':'GameCam-VO-Evidence-Delivery',
            'Accept':'application/vnd.github+json','Content-Type':'application/zip' if path.suffix=='.zip' else 'text/plain',
            'Content-Length':str(path.stat().st_size)}.items():conn.putheader(key,value)
        conn.endheaders();sent=0;next_notice=64*1024**2
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1024**2),b''):
                conn.send(block);sent+=len(block)
                if sent>=next_notice:print('UPLOAD_PROGRESS',path.name,sent,flush=True);next_notice+=64*1024**2
        response=conn.getresponse();body=response.read()
        if response.status not in [200,201]:raise RuntimeError(f'GitHub asset upload returned HTTP{response.status}')
        result=json.loads(body)
    finally:conn.close()
    if result.get('digest')!='sha256:'+actual or result.get('size')!=path.stat().st_size or result.get('state')!='uploaded':
        raise RuntimeError('GitHub server asset digest/size/state mismatch')
    return {k:result[k] for k in ['id','name','size','state','digest','browser_download_url']}


def main():
    p=argparse.ArgumentParser();p.add_argument('--finalize-commit');a=p.parse_args()
    PRIVATE.mkdir(parents=True,exist_ok=True);receipt_path=PRIVATE/'raw_release_receipt.json'
    metadata=api('GET','')
    if metadata['id']!=1450634998 or metadata['private'] or metadata['default_branch']!='codex/research-review-20261124':
        raise RuntimeError('Repository identity/visibility/default branch differs; do not change it')
    token=credentials()
    if receipt_path.exists():
        receipt=json.loads(receipt_path.read_text());release=api('GET','/releases/'+str(receipt['release_id']),token)
        if release['tag_name']!=TAG or not release['draft']:raise RuntimeError('Existing release is not this task draft; never overwrite published releases')
    else:
        release=api('POST','/releases',token,{'tag_name':TAG,'target_commitish':'ff0c9ed761dbcdd6d2fe7b2cda5651c6e173efe1',
            'name':'TASK010-A dynamic-prior / geometry / depth investigation','draft':True,'prerelease':True,
            'body':'Evidence upload in progress. Model weights and original datasets are excluded. Final results will be fixed to the reviewed commit.','make_latest':'false'})
        receipt={'release_id':release['id'],'tag':TAG,'draft':True,'uploaded':[],'visibility_changed':False,'default_branch_changed':False}
        receipt_path.write_text(json.dumps(receipt,indent=2))
    assets=json.loads((TASK/'private/RAW_ASSET_UPLOAD_MANIFEST.json').read_text())
    if a.finalize_commit:
        commit=api('GET','/commits/'+a.finalize_commit)
        if commit['sha']!=a.finalize_commit:raise RuntimeError('Final commit identity mismatch')
        main_zip=ROOT/'review_packages/GAMECAM_TASK010A_REVIEW.zip'
        checksums=ROOT/'deliveries/TASK010A_RAW/RAW_EVIDENCE_SHA256SUMS.txt'
        checksums.write_text(''.join(x['sha256']+'  '+Path(x['source']).name+'\n' for x in assets))
        assets.extend([{'source':str(main_zip),'sha256':sha(main_zip)},
            {'source':str(main_zip.with_suffix('.zip.sha256')),'sha256':sha(main_zip.with_suffix('.zip.sha256'))},
            {'source':str(checksums),'sha256':sha(checksums)}])
    existing={x['name']:x for x in api('GET','/releases/'+str(release['id'])+'/assets?per_page=100',token)}
    for asset in assets:
        name=Path(asset['source']).name
        if name in existing:
            result=existing[name]
            if result.get('digest')!='sha256:'+asset['sha256'] or result.get('state')!='uploaded':
                raise RuntimeError('Existing task asset differs; do not delete or overwrite')
            result={k:result[k] for k in ['id','name','size','state','digest','browser_download_url']}
        else:result=upload(asset,release,token)
        if not any(r['name']==name for r in receipt['uploaded']):receipt['uploaded'].append(result)
        receipt_path.write_text(json.dumps(receipt,indent=2));print('ASSET_VERIFIED',name,result['size'],flush=True)
    if not a.finalize_commit:
        print('ALL_RAW_ASSETS_UPLOADED_TO_NEW_DRAFT; no existing release changed',flush=True);return
    # Do not retarget an existing Git tag. A newly created draft normally has no tag.
    try:ref=api('GET','/git/ref/tags/'+TAG,token)
    except RuntimeError as e:
        if 'HTTP404' not in str(e):raise
    else:
        if ref['object']['sha']!=a.finalize_commit:raise RuntimeError('Task tag points elsewhere; never force-update it')
    body=(TASK/'08_reports/RELEASE_BODY.md').read_text(encoding='utf-8')
    final=api('PATCH','/releases/'+str(release['id']),token,{'target_commitish':a.finalize_commit,'draft':False,
        'prerelease':True,'make_latest':'false','body':body})
    public=api('GET','/releases/tags/'+TAG)
    if public['draft'] or len(public['assets'])!=len(assets):raise RuntimeError('Public release missing expected assets')
    for asset in assets:
        actual=next(x for x in public['assets'] if x['name']==Path(asset['source']).name)
        if actual.get('digest')!='sha256:'+asset['sha256']:raise RuntimeError('Public server digest mismatch')
    ref=api('GET','/git/ref/tags/'+TAG)
    if ref['object']['sha']!=a.finalize_commit:raise RuntimeError('Published tag identity mismatch')
    receipt.update(draft=False,status='PUBLIC_VERIFIED',commit=a.finalize_commit,
        public_url=public['html_url'],public_asset_digests_all_pass=True)
    receipt_path.write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
