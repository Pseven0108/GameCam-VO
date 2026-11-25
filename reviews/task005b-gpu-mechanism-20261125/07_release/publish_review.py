"""Publish a stopped-results review without modifying prior branch histories."""
import os,sys,pathlib,json,shutil,subprocess,urllib.request,urllib.error,urllib.parse,hashlib,zipfile,argparse
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'07_release'))
from package_review import sha,preserve_prior
sys.path.insert(0,r'D:\aaa\GameCam-VO\maintenance\GITHUB_REVIEW_PUBLICATION_20261124_R1')
from github_readonly import credential,api
RECEIVER=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-GPU-20261125-R1')
SOURCE=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125\publication_repository_task005b_preparation')
REPO=RECEIVER/'publication_repository_task005b_gpu_mechanism'
SLUG='task005b-gpu-mechanism-20261125';BRANCH='codex/'+SLUG;REL='reviews/'+SLUG
PARENT='f5182e98b043ee1e9bebd64b5ac2dda3e294ade8'
BASE='/repos/Pseven0108/GameCam-VO'
ENV=dict(os.environ,GCM_INTERACTIVE='Never',GIT_TERMINAL_PROMPT='0',CUDA_VISIBLE_DEVICES='')

def cmd(args,timeout=180):
    p=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',env=ENV,timeout=timeout)
    if p.returncode:raise RuntimeError({'program':args[0],'exit':p.returncode,'stderr':p.stderr[-1200:]})
    return p.stdout.strip()
def git(*args,timeout=180):return cmd(['git','-C',str(REPO),*args],timeout)
def save(name,data):(ROOT/'07_release'/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def read(name):return json.loads((ROOT/'07_release'/name).read_text(encoding='utf-8-sig'))
def protected(token):
    want=read('GITHUB_INTAKE.json')['protected_prior_refs'];found={}
    for ref,expected in want.items():
        found[ref]=api(BASE+'/git/ref/'+ref.removeprefix('refs/'),token)['object']['sha']
        assert found[ref]==expected,(ref,found[ref])
    return found

def prepare():
    package=read('PACKAGE_VALIDATION.json');assert package['status']=='PASS'
    assert package['scientific_status']=='STOPPED_ENDPOINT_EQUIVALENCE_FAILURE'
    preserve_prior();token=credential();before=api(BASE,token);refs=protected(token)
    try:
        api(BASE+'/git/ref/heads/'+BRANCH,token)
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
    else:raise RuntimeError('Publication branch already exists; inspect receipt before proceeding')
    assert not REPO.exists(),'Do not overwrite a publication checkout'
    cmd(['git','clone','--no-hardlinks','--no-checkout',str(SOURCE),str(REPO)],300)
    git('config','core.longpaths','true');git('remote','set-url','origin','https://github.com/Pseven0108/GameCam-VO.git')
    git('checkout','-b',BRANCH,PARENT)
    for key in ('user.name','user.email'):git('config',key,cmd(['git','-C',str(SOURCE),'config','--get',key]))
    assert not git('status','--porcelain')
    shutil.copytree(package['expanded_review'],REPO/REL)
    zurl='https://github.com/Pseven0108/GameCam-VO/releases/download/'+SLUG+'/'+package['ZIP']
    status=f'''# GameCam-VO · TASK005B GPU partial results

TASK005B stopped at the preregistered native endpoint-equivalence guard. Two of four prefixes completed; six real inputs captured; four replay contexts complete and one partial. Executed 58/144 two-iteration native BA calls. D0_S1_RGB233 / NATIVE_UPDATE_D failed at the original dx/dz tolerance. No numerical retry or tolerance change was made. S0 was not run; the S1/S0 reversal is not explained.

Task004C-B, Task005A and the CPU preparation reviews remain sealed. No Task005C/006 and no instance shutdown.

[Final review]({REL}/FINAL_REVIEW.md) · [Decision]({REL}/TASK005B_DECISION.json) · [Review ZIP]({zurl}) · [Complete raw native arrays and run logs](https://github.com/Pseven0108/GameCam-VO/releases/tag/{SLUG})
'''
    for name in ('README.md','PROJECT_STATUS.md'):(REPO/name).write_text(status,encoding='utf-8')
    idx=REPO/'REVIEW_INDEX.md';prior=idx.read_text(encoding='utf-8') if idx.exists() else ''
    idx.write_text(f'# Latest GPU partial-results review\n\n[{SLUG}]({REL}/FINAL_REVIEW.md) · [ZIP]({zurl}) · [all native data assets](https://github.com/Pseven0108/GameCam-VO/releases/tag/{SLUG}).\n\n---\n\n'+prior,encoding='utf-8')
    git('add','--',REL,'README.md','PROJECT_STATUS.md','REVIEW_INDEX.md')
    # A global ignore rule must not silently drop a numeric review artifact.
    review_manifest=json.loads((REPO/REL/'FILE_SHA256_MANIFEST.json').read_text(encoding='utf-8'))['files']
    for path in (REPO/REL).rglob('*'):
        if path.is_file():
            listed=git('ls-files','--',path.relative_to(REPO).as_posix())
            if not listed:
                relative=path.relative_to(REPO/REL).as_posix()
                assert relative.startswith('05_analysis/reduced_native/') and path.suffix=='.npz'
                assert path.stat().st_size<8*1024**2 and sha(path)==review_manifest[relative]['sha256']
                git('add','-f','--',path.relative_to(REPO).as_posix())
            assert git('ls-files','--',path.relative_to(REPO).as_posix())
    git('commit','-m','Preserve TASK005B GPU partial evidence after native endpoint mismatch')
    head=git('rev-parse','HEAD')
    for prior_dir in ('task004c-b-crossover-full-20261125','task005a-d-schedule-mechanism-20261125','task005b-depth-path-preparation-20261125'):
        path='reviews/'+prior_dir
        assert git('rev-parse',PARENT+':'+path)==git('rev-parse',head+':'+path)
    proof={'artifact_commit':head,'branch':BRANCH,'prepared':True,'published':False,'repository':str(REPO),
           'repository_private_before':before['private'],'default_branch_before':before['default_branch'],
           'protected_prior_refs':refs,'package':package,'review_files':sum(p.is_file() for p in (REPO/REL).rglob('*'))}
    save('GITHUB_PREPARED.json',proof);print(json.dumps(proof,indent=2))

def verify_asset(asset,want):
    assert asset['state']=='uploaded' and asset['size']==want['bytes']
    assert asset.get('digest')=='sha256:'+want['sha256'],('Release asset digest missing or different',asset['name'])

def publish():
    prepared=read('GITHUB_PREPARED.json');package=read('PACKAGE_VALIDATION.json')
    head=prepared['artifact_commit'];token=credential();protected(token);preserve_prior()
    assert git('rev-parse','HEAD')==head and not git('status','--porcelain')
    assert sha(package['ZIP_path'])==package['ZIP_sha256']
    # Permit only this exact new branch; no force-push, no default-branch writes.
    existing=git('ls-remote','--heads','origin','refs/heads/'+BRANCH)
    if existing:assert existing.split()[0]==head
    else:git('push','-u','origin',BRANCH,timeout=600)
    assert git('ls-remote','--heads','origin','refs/heads/'+BRANCH).split()[0]==head
    tree=api(BASE+'/git/trees/'+head+'?recursive=1',token);assert not tree.get('truncated')
    blobs={v['path']:v['sha'] for v in tree['tree'] if v['type']=='blob'}
    count=0
    for path in (REPO/REL).rglob('*'):
        if path.is_file():
            raw=path.read_bytes();want=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            assert blobs[path.relative_to(REPO).as_posix()]==want;count+=1
    try:release=api(BASE+'/releases/tags/'+SLUG,token)
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
        release=api(BASE+'/releases',token,method='POST',body={'tag_name':SLUG,'target_commitish':head,
            'name':'TASK005B GPU mechanism — stopped endpoint-equivalence review',
            'body':'PARTIAL RESULTS. 2/4 prefixes, 6 real inputs, 4 complete replay contexts, one failed endpoint at D0_S1_RGB233. 58/144 native two-iteration calls; 19 endpoint checks passed, one failed. No tolerance change or numerical retry. Includes the complete review ZIP, four complete raw traces, the preserved failed trace, and full run logs. S0 not run; mechanism reversal not established.',
            'draft':False,'prerelease':True})
    assert release['tag_name']==SLUG and release['target_commitish']==head
    items=[{'name':package['ZIP'],'path':package['ZIP_path'],'bytes':package['ZIP_bytes'],'sha256':package['ZIP_sha256']}]
    for entry in read('RAW_ASSET_INDEX.json')['assets']:items.append({**entry,'path':str(RECEIVER/entry['name'])})
    uploaded=[]
    for item in items:
        path=pathlib.Path(item['path']);assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
        current=api(BASE+'/releases/'+str(release['id'])+'/assets',token)
        assets=[a for a in current if a['name']==item['name']];assert len(assets)<=1
        if assets:asset=assets[0];verify_asset(asset,item)
        else:
            url=release['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(item['name'])
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/zip' if path.suffix=='.zip' else 'application/octet-stream',
                     'Content-Length':str(item['bytes']),'User-Agent':'GameCam-VO-review-publication'}
            with path.open('rb') as stream:
                request=urllib.request.Request(url,data=stream,method='POST',headers=headers)
                with urllib.request.urlopen(request,timeout=600) as response:asset=json.load(response)
            verify_asset(asset,item)
        uploaded.append({'name':item['name'],'bytes':asset['size'],'sha256':item['sha256'],'GitHub_digest':asset['digest'],'URL':asset['browser_download_url'],'id':asset['id']})
        save('GITHUB_ASSET_UPLOAD_PROGRESS.json',{'artifact_commit':head,'release_id':release['id'],'uploaded':uploaded})
        print(json.dumps({'event':'ASSET_DIGEST_VERIFIED','asset':item['name'],'bytes':item['bytes']}),flush=True)
    after=api(BASE,token);protected(token)
    assert (after['private'],after['default_branch'])==(prepared['repository_private_before'],prepared['default_branch_before'])
    receipt={'published':True,'artifact_commit':head,'branch':BRANCH,'release_id':release['id'],'release_tag':SLUG,
             'review_URL':'https://github.com/Pseven0108/GameCam-VO/blob/'+head+'/'+REL+'/FINAL_REVIEW.md',
             'directory_URL':'https://github.com/Pseven0108/GameCam-VO/tree/'+head+'/'+REL,
             'release_URL':release['html_url'],'ZIP_URL':uploaded[0]['URL'],'ZIP_sha256':package['ZIP_sha256'],
             'remote_review_blobs_verified':count,'release_assets':uploaded,'prior_task_refs_preserved':True,
             'visibility_or_default_branch_changed':False,'scientific_status':'STOPPED_ENDPOINT_EQUIVALENCE_FAILURE'}
    save('GITHUB_PUBLICATION_RECEIPT.json',receipt)
    print(json.dumps(receipt,indent=2))

def verify_anonymous():
    receipt=read('GITHUB_PUBLICATION_RECEIPT.json');prepared=read('GITHUB_PREPARED.json');assert not prepared['repository_private_before']
    ua={'User-Agent':'GameCam-VO-anonymous-review-verification'}
    p=ROOT/'07_release/ANONYMOUS_DOWNLOAD_VERIFICATION.zip'
    if p.exists():assert sha(p)==receipt['ZIP_sha256']
    else:
        with urllib.request.urlopen(urllib.request.Request(receipt['ZIP_URL'],headers=ua),timeout=180) as r,p.open('xb') as out:shutil.copyfileobj(r,out)
    assert sha(p)==receipt['ZIP_sha256']
    with zipfile.ZipFile(p) as archive:
        assert archive.testzip() is None
        manifest=json.loads(archive.read('FILE_SHA256_MANIFEST.json'))['files']
        assert set(archive.namelist())==set(manifest)|{'FILE_SHA256_MANIFEST.json'}
        for name,proof in manifest.items():
            data=archive.read(name);assert len(data)==proof['bytes'] and hashlib.sha256(data).hexdigest()==proof['sha256']
    raw_checks=[]
    for name in ('FINAL_REVIEW.md','TASK005B_DECISION.json','05_analysis/ENDPOINT_FAILURE_FORENSICS.json','05_analysis/FAILED_CONTEXT_LINEAR_DIAGNOSTICS.json'):
        url='https://raw.githubusercontent.com/Pseven0108/GameCam-VO/'+receipt['artifact_commit']+'/'+REL+'/'+name
        with urllib.request.urlopen(urllib.request.Request(url,headers=ua),timeout=90) as r:data=r.read()
        assert data==(REPO/REL/name).read_bytes();raw_checks.append(name)
    with urllib.request.urlopen(urllib.request.Request('https://api.github.com'+BASE+'/releases/'+str(receipt['release_id'])+'/assets',headers=ua),timeout=90) as r:public_assets=json.load(r)
    assets={a['name']:a for a in public_assets}
    for want in receipt['release_assets']:verify_asset(assets[want['name']],want)
    proof={'anonymous_ZIP_SHA_CRC_and_all_member_SHA':'PASS','manifest_items':len(manifest),'anonymous_fixed_commit_raw_files':raw_checks,
           'all_7_public_assets_SHA256_digest_matches':True,'complete_large_assets_not_redownloaded':True,
           'large_asset_verification':'GitHub server-side SHA256 digest and byte size matched local immutable archives; public asset metadata independently verified.'}
    receipt['anonymous_verification']=proof;save('GITHUB_PUBLICATION_RECEIPT.json',receipt)
    ops=REPO/'operations'/SLUG;ops.mkdir(parents=True,exist_ok=False)
    (ops/'PUBLICATION_VERIFICATION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    git('add','--','operations/'+SLUG+'/PUBLICATION_VERIFICATION.json');git('commit','-m','Record verified partial-results archive publication')
    receipt['receipt_commit']=git('rev-parse','HEAD');git('push','origin',BRANCH,timeout=300)
    save('GITHUB_PUBLICATION_RECEIPT.json',receipt);preserve_prior();print(json.dumps(receipt,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','publish','verify-anonymous']);args=parser.parse_args()
    {'prepare':prepare,'publish':publish,'verify-anonymous':verify_anonymous}[args.action]()
