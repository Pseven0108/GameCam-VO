"""Publish stopped-batch evidence with server-scoped credentials, then verify."""
import base64,csv,datetime,hashlib,importlib.util,io,json,os,re,subprocess,sys,time,zipfile
from pathlib import Path
from urllib.request import Request,urlopen
from common import TASK,ROOT,REVIEW,PARENT,dump,sha

# The existing helper sends operations through pinned SSH. Credentials stay on
# the authorized server; no credential or repository visibility is modified.
spec=importlib.util.spec_from_file_location('sealed_publication_transport',TASK.parent/'TASK011D/publish_review.py')
transport=importlib.util.module_from_spec(spec);spec.loader.exec_module(transport)
api=transport.api
PRIVATE=TASK/'private/publication'
REPO='Pseven0108/GameCam-VO'

def git(*args):
    p=subprocess.run(['git',*args],cwd=ROOT,capture_output=True)
    if p.returncode:raise RuntimeError('Local Git operation failed: '+args[0])
    return p.stdout.decode('utf-8').strip()

def person(line):
    m=re.fullmatch(r'(.*) <(.*)> (\d+) ([+-]\d{4})',line)
    if not m:raise ValueError('Unknown Git identity format')
    name,email,stamp,offset=m.groups();sign=1 if offset[0]=='+' else -1
    zone=datetime.timezone(sign*datetime.timedelta(hours=int(offset[1:3]),minutes=int(offset[3:5])))
    return dict(name=name,email=email,date=datetime.datetime.fromtimestamp(int(stamp),zone).isoformat())

def push_api(manifest,commit):
    raw=git('cat-file','-p',commit);header,message=raw.split('\n\n',1)
    h={line.split(' ',1)[0]:line.split(' ',1)[1] for line in header.splitlines()}
    modes={line.split()[3]:line.split()[0] for line in git('ls-files','--stage').splitlines()}
    entries=[]
    for r in manifest['entries']:
        entries.append(dict(path=r['path'],mode=modes[r['path']],type='blob',sha=r['git_blob_sha'],
            content=base64.b64encode(Path(r['source']).read_bytes()).decode()))
    payload=dict(parent=PARENT,branch=manifest['branch'],commit=commit,tree=h['tree'],
        commit_body=dict(message=message,parents=[PARENT],author=person(h['author']),committer=person(h['committer'])),entries=entries)
    code=r'''
import base64,json,subprocess,sys
x=json.load(sys.stdin)
def api(method,path,value=None):
 args=['/usr/local/bin/gamecam-gh','api','repos/Pseven0108/GameCam-VO'+path,'--method',method]
 data=None
 if value is not None:args+=['--input','-'];data=json.dumps(value).encode()
 p=subprocess.run(args,input=data,capture_output=True,timeout=90)
 if p.returncode:raise RuntimeError('Scoped GitHub operation failed: '+path)
 return json.loads(p.stdout)
parent=api('GET','/git/commits/'+x['parent']);tree=api('GET','/git/trees/'+parent['tree']['sha']+'?recursive=1')
if tree.get('truncated'):raise RuntimeError('Parent tree truncated')
known={r['sha'] for r in tree['tree'] if r['type']=='blob'};created=0
for r in x['entries']:
 if r['sha'] in known:continue
 b=api('POST','/git/blobs',dict(content=r['content'],encoding='base64'))
 if b['sha']!=r['sha']:raise RuntimeError('Blob identity mismatch')
 known.add(b['sha']);created+=1
new=api('POST','/git/trees',dict(base_tree=parent['tree']['sha'],tree=[{k:r[k] for k in ['path','mode','type','sha']} for r in x['entries']]))
if new['sha']!=x['tree']:raise RuntimeError('Remote tree differs from local tree')
body=dict(x['commit_body'],tree=new['sha']);c=api('POST','/git/commits',body)
if c['sha']!=x['commit']:raise RuntimeError('Remote commit identity mismatch')
ref=api('POST','/git/refs',dict(ref='refs/heads/'+x['branch'],sha=c['sha']))
if ref['object']['sha']!=x['commit']:raise RuntimeError('Branch identity mismatch')
print(json.dumps(dict(status='PUSHED',commit=c['sha'],tree=new['sha'],created_blobs=created,credential_exported=False,force_push=False)))
'''
    p=subprocess.run(transport.command(code),input=json.dumps(payload).encode(),capture_output=True,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
    if p.returncode:raise RuntimeError('Scoped API publication failed; preserved state: '+p.stderr.decode('utf-8','replace')[-1200:])
    return json.loads(p.stdout)

def main():
    m=json.loads((PRIVATE/'allowlist.json').read_text());rp=PRIVATE/'PUBLICATION_RECEIPT.json'
    receipt=json.loads(rp.read_text()) if rp.exists() else {}
    metadata=api('GET','?verify='+str(time.time_ns()))
    if metadata['id']!=1450634998 or metadata['private'] or metadata['full_name'].lower()!=REPO.lower():raise RuntimeError('Public repository identity changed')
    receipt.setdefault('original_default_branch',metadata['default_branch'])
    if 'commit' not in receipt:
        if git('rev-parse','HEAD')!=PARENT or git('branch','--show-current')!=m['branch'] or git('diff','--cached','--name-only'):
            raise RuntimeError('Preserve unexpected Git work')
        for r in m['entries']:
            if sha(r['source'])!=r['sha256']:raise RuntimeError('Publication allowlist drift')
        paths=PRIVATE/'paths.nul';paths.write_bytes(b''.join(r['path'].encode()+b'\0' for r in m['entries']))
        git('--literal-pathspecs','add','--sparse','-f','--pathspec-from-file='+str(paths),'--pathspec-file-nul')
        if set(git('diff','--cached','--name-only').splitlines())!={r['path'] for r in m['entries']}:raise RuntimeError('Staged allowlist differs')
        message=PRIVATE/'COMMIT_MESSAGE.txt';message.write_text('TASK011E: run frozen cache preparation; preserve storage safety stop\n\nRTX3090 admission passed; 5 caches complete, 16 partial frames; E2E 0/285.\n',encoding='utf-8')
        git('commit','-F',str(message));receipt.update(status='COMMITTED_NOT_PUSHED',commit=git('rev-parse','HEAD'),tree=git('rev-parse','HEAD^{tree}'))
        dump(rp,receipt)
    if receipt['status']=='COMMITTED_NOT_PUSHED':
        print('PUBLISHING_STOPPED_BATCH_EVIDENCE',receipt['commit'],flush=True)
        dump(PRIVATE/'SERVER_API_PUSH_RECEIPT.json',push_api(m,receipt['commit']))
        receipt['status']='PUSHED';dump(rp,receipt)
    commit=receipt['commit'];tree=api('GET','/git/trees/'+receipt['tree']+'?recursive=1&verify='+str(time.time_ns()))
    if tree.get('truncated'):raise RuntimeError('Published tree truncated')
    blobs={r['path']:r['sha'] for r in tree['tree'] if r['type']=='blob'}
    if any(blobs.get(r['path'])!=r['git_blob_sha'] for r in m['entries']):raise RuntimeError('Published blob mismatch')
    final_url='https://raw.githubusercontent.com/'+REPO+'/'+commit+'/'+m['review_directory']+'/FINAL_REVIEW.md'
    with urlopen(Request(final_url,headers={'User-Agent':'GameCam-VO-Verification'}),timeout=45) as f:
        if f.read()!=(REVIEW/'FINAL_REVIEW.md').read_bytes():raise RuntimeError('Public final report differs')
    if 'release_id' not in receipt:
        release=api('POST','/releases',dict(tag_name=m['release_tag'],target_commitish=commit,
            name='TASK011E — actual GPU cache execution / storage safety stop',draft=True,prerelease=True,make_latest='false',
            body='GPU admission passed. Five complete caches and 16 partial frames preserved. E2E 0/285. Complete evidence uploading.'))
        receipt['release_id']=release['id'];dump(rp,receipt)
    else:release=api('GET','/releases/'+str(receipt['release_id']))
    paths=[Path(m['archive']),Path(m['archive']+'.sha256')]
    assets=api('GET','/releases/'+str(receipt['release_id'])+'/assets?per_page=100')
    for path in paths:
        prior=next((r for r in assets if r['name']==path.name),None)
        if prior:
            if prior['digest']!='sha256:'+sha(path) or prior['size']!=path.stat().st_size:raise RuntimeError('Existing asset mismatch')
        else:transport.upload(path,release)
    body=f'''Actual RTX3090 execution checkpoint: **STOPPED_STORAGE**. Fast native environment/adapter and four model identities passed. Five complete64-frame common caches plus16 partial frames are preserved. Formal E2E **0/285**; no Canary or algorithm accuracy result.

The next cache write could not retain the10GiB safety floor. No historical deletion, automatic retry, baseline change, CUDA rebuild or shutdown. Secondary thresholds remain unapproved; FSR deferred.

- [Fixed-commit full review](https://github.com/{REPO}/blob/{commit}/{m['review_directory']}/FINAL_REVIEW.md)
- [Complete expanded review](https://github.com/{REPO}/tree/{commit}/{m['review_directory']})

Full original ZIP includes code, frozen contracts,14 targeted launch tests, real logs, per-file cache inventory and disk-stop evidence. Large cache arrays remain on the server with their SHA256 inventory; datasets, weights, environments and credentials are excluded. Expand storage and explicitly confirm preserved-cache continuation; no automatic retry is granted by publication.
'''
    if release['draft']:api('PATCH','/releases/'+str(receipt['release_id']),dict(draft=False,prerelease=True,make_latest='false',body=body))
    public=api('GET','/releases/tags/'+m['release_tag']+'?verify='+str(time.time_ns()))
    ref=api('GET','/git/ref/tags/'+m['release_tag'])
    if public['draft'] or ref['object']['sha']!=commit or len(public['assets'])!=2:raise RuntimeError('Public release/tag mismatch')
    asset=next(r for r in public['assets'] if r['name']==paths[0].name)
    if asset['digest']!='sha256:'+m['archive_sha256']:raise RuntimeError('Public ZIP digest mismatch')
    verify=PRIVATE/'PUBLIC_ZIP_VERIFICATION.zip'
    if verify.exists():raise RuntimeError('Preserve prior verification file')
    print('VERIFYING_PUBLIC_COMPLETE_ZIP',asset['size'],flush=True)
    with urlopen(Request(asset['browser_download_url'],headers={'User-Agent':'GameCam-VO-Verification'}),timeout=90) as f,verify.open('xb') as out:
        for b in iter(lambda:f.read(1024**2),b''):out.write(b)
    if sha(verify)!=m['archive_sha256'] or verify.stat().st_size!=asset['size']:raise RuntimeError('Anonymous download mismatch')
    with zipfile.ZipFile(verify) as z:
        if z.testzip() is not None:raise RuntimeError('Public ZIP CRC failure')
        rows=list(csv.DictReader(io.StringIO(z.read('SHA256_MANIFEST.csv').decode())))
        if len(rows)!=m['internal_sha256_count']:raise RuntimeError('Public manifest count mismatch')
        for r in rows:
            raw=z.read(r['path'])
            if len(raw)!=int(r['bytes']) or hashlib.sha256(raw).hexdigest()!=r['sha256']:raise RuntimeError('Public internal SHA failure')
    after=api('GET','?verify='+str(time.time_ns()))
    if after['private'] or after['default_branch']!=receipt['original_default_branch']:raise RuntimeError('Repository visibility/default branch drift')
    receipt.update(status='PUBLIC_VERIFIED',ZIP_CRC='PASS',internal_sha256_verified=len(rows),public_blob_identities_verified=len(m['entries']),
        zip_sha256=sha(verify),zip_bytes=verify.stat().st_size,anonymous_public_download=True,release_url=public['html_url'],
        zip_public_url=asset['browser_download_url'],final_review_url='https://github.com/'+REPO+'/blob/'+commit+'/'+m['review_directory']+'/FINAL_REVIEW.md',
        research_status='STOPPED_STORAGE',complete_caches=5,partial_cache_frames=16,E2E_attempts=0,FSR_runs=0,
        server_credentials_exported=False,visibility_changed=False,default_branch_changed=False)
    dump(rp,receipt)
    if paths[0].resolve().parent!=(ROOT/'review_packages').resolve() or sha(paths[0])!=receipt['zip_sha256']:raise RuntimeError('ZIP cleanup identity mismatch')
    paths[0].unlink();verify.unlink()
    receipt.update(current_local_complete_review_ZIP_removed=True,expanded_reports_and_original_evidence_retained=True)
    dump(rp,receipt);print(json.dumps(receipt,indent=2),flush=True)

if __name__=='__main__':main()
