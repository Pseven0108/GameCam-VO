"""Publish one exact TASK008 tree/Release using the existing scoped credential helper."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

P=json.load(sys.stdin);REPO='Pseven0108/GameCam-VO'
BASE='3bf7da7bb39192081cefe9898e948784ae6cd5aa'
SLUG='task008-pi3mos-night007-independent-inference-20261126';BRANCH='codex/'+SLUG
PREFIX='reviews/'+SLUG+'/'
STAGE=Path('/root/rivermind-data/GAMECAM_TASK008_PUBLICATION_20261126');STAGE.mkdir(mode=0o700,exist_ok=False)
STATE={};ENV=dict(os.environ)
for key in ['GIT_TRACE','GIT_TRACE_CURL','GIT_CURL_VERBOSE','GH_DEBUG']:ENV.pop(key,None)
ENV.update(GIT_TERMINAL_PROMPT='0',GIT_LFS_SKIP_SMUDGE='1',PYTHONDONTWRITEBYTECODE='1')

def remember(key,value):
    STATE[key]=value;(STAGE/'PROGRESS.json').write_text(json.dumps(STATE,indent=2)+'\n')

def api(path,method='GET',data=None,binary=None):
    args=['/usr/local/bin/gamecam-gh','api',path,'--method',method];body=None
    if data is not None:args+=['--input','-'];body=json.dumps(data).encode()
    if binary is not None:args+=['--input',str(binary),'-H','Content-Type: application/octet-stream']
    r=subprocess.run(args,input=body,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180,env=ENV)
    if r.returncode:raise RuntimeError('GitHub API stage failed: '+method+' '+path.split('?')[0]+'; arbitrary diagnostics withheld')
    return json.loads(r.stdout) if r.stdout else None

work=STAGE/'repo';work.mkdir()

def git(args,label,input_data=None,timeout=180):
    r=subprocess.run(['git','-C',str(work),*args],input=input_data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,env=ENV)
    with (STAGE/(label+'.stdout.txt')).open('xb') as f:f.write(r.stdout)
    with (STAGE/(label+'.stderr.txt')).open('xb') as f:f.write(r.stderr)
    if r.returncode:raise RuntimeError('Git publication failed at '+label+'; original workspace preserved')
    return r.stdout.decode('utf-8').strip()

def blob_sha(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()

repo=api('repos/'+REPO)
assert repo['visibility']=='public' and repo['default_branch']=='codex/research-review-20261124'
git(['init'],'INIT')
git(['config','user.name','GameCam-VO Review'],'USER_NAME')
git(['config','user.email','gamecam-vo-review@users.noreply.github.com'],'USER_EMAIL')
git(['config','core.autocrlf','false'],'LINE_ENDINGS')
# This helper returns credentials only into Git's internal pipe. No token in argv/output/reports.
git(['config','credential.helper','!/usr/local/bin/gamecam-gh auth git-credential'],'CREDENTIAL_HELPER')
git(['remote','add','origin','https://github.com/'+REPO+'.git'],'ADD_REMOTE')
assert not git(['ls-remote','--heads','origin','refs/heads/'+BRANCH],'CHECK_NEW_BRANCH')
remember('stage','FETCH_BASE_TREE_ONLY')
git(['fetch','--filter=blob:none','--depth=1','--no-tags','origin',BASE],'FETCH_BASE',timeout=240)
git(['read-tree',BASE],'READ_BASE_INDEX')
all_rows=[]
for row in P['files']:
    row={**row,'path':PREFIX+row['path']};all_rows.append(row)
all_rows+=P['project_files']
for i,row in enumerate(P['state_entries']):
    assert row['path'] in ['README.md','PROJECT_STATUS.md','REVIEW_INDEX.md','REVIEWING.md']
    actual=git(['rev-parse',BASE+':'+row['path']],'CHECK_STATE_'+str(i))
    assert actual==row['base_sha']
    all_rows.append(row)
paths=[];expanded=[]
for row in all_rows:
    rel=Path(row['path']);assert not rel.is_absolute() and '..' not in rel.parts and '.git' not in rel.parts
    b=base64.b64decode(row['base64']);assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256']
    p=work/rel;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(b)
    paths.append(row['path']);expanded.append({'path':row['path'],'sha':blob_sha(b),'sha256':row['sha256'],'bytes':len(b)})
assert len(set(paths))==len(paths)
remember('stage','STAGE_EXACT_REVIEW_FILES')
git(['add','--',*paths],'ADD_EXACT_FILES')
tree=git(['write-tree'],'WRITE_TREE');remember('tree',tree)
commit=git(['commit-tree',tree,'-p',BASE], 'CREATE_COMMIT',input_data=b'Validate standalone Pi3MOS dynamic prior on32 Night007 targets with3/5-frame inputs; preserve limited qualitative interpretation\n')
remember('commit',commit)
changed=git(['diff-tree','--no-commit-id','--name-only','-r',commit],'VERIFY_EXACT_CHANGED_PATHS').splitlines()
assert set(changed)==set(paths),'Unplanned repository path changes; stop before push'
remember('stage','PUSH_REVIEW_BRANCH')
git(['push','origin',commit+':refs/heads/'+BRANCH],'PUSH_BRANCH',timeout=300)
remember('branch',BRANCH)
raw=base64.b64decode(P['ZIP_base64']);archive=STAGE/P['ZIP']['ZIP_name']
assert len(raw)==P['ZIP']['ZIP_bytes'] and hashlib.sha256(raw).hexdigest()==P['ZIP']['ZIP_sha256']
with archive.open('xb') as f:f.write(raw)
body=('TASK008 standalone official Pi3MOS inference on VIPER Night007 RGB301-332 complete:3-frame32/32 and5-frame32/32,64 forwards, strict official safetensors loading, BF16 RTX3090, no OOM. '
      'Vehicle masks are visually continuous; five-frame superiority and detection accuracy are not established. No parked-vehicle/pedestrian/pure-rotation controls. '
      'Includes complete review,384 derived per-frame views, contact sheets, all statistics, input/raw-array identities, code and full deployment/runtime logs. '
      'Original RGB,821MB float32 NPZ, model weights and environments remain private on local/server storage and are excluded from public assets. '
      'No DROID-W/Metric3D/BA integration, no training, no automatic next stage.\n\nZIP SHA256: '+P['ZIP']['ZIP_sha256'])
release=api('repos/'+REPO+'/releases','POST',{'tag_name':SLUG,'target_commitish':commit,
    'name':'TASK008 Pi3MOS Night007 Independent Inference and Visual Validation','body':body,'draft':True,'prerelease':True})
remember('draft_release_id',release['id'])
asset=api(release['upload_url'].split('{')[0]+'?name='+archive.name,'POST',binary=archive)
assert asset['state']=='uploaded' and asset['size']==len(raw) and asset['digest']=='sha256:'+P['ZIP']['ZIP_sha256']
remember('ZIP_asset',{'id':asset['id'],'bytes':len(raw),'sha256':P['ZIP']['ZIP_sha256']})
sidecar=STAGE/(archive.name+'.sha256');sidecar.write_text(P['ZIP']['ZIP_sha256']+'  '+archive.name+'\n')
sha_asset=api(release['upload_url'].split('{')[0]+'?name='+sidecar.name,'POST',binary=sidecar)
assert sha_asset['state']=='uploaded'
release=api('repos/'+REPO+'/releases/'+str(release['id']),'PATCH',{'draft':False,'prerelease':True})
final=api('repos/'+REPO);assert final['visibility']=='public' and final['default_branch']==repo['default_branch']
receipt={'state':'PUBLISHED_AWAITING_ANONYMOUS_READBACK','repository':REPO,'commit':commit,'branch':BRANCH,'tag':SLUG,
    'ZIP':P['ZIP'],'ZIP_url':asset['browser_download_url'],'release_url':release['html_url'],
    'report_url':'https://github.com/'+REPO+'/blob/'+commit+'/'+PREFIX+'FINAL_REVIEW.md',
    'directory_url':'https://github.com/'+REPO+'/tree/'+commit+'/'+PREFIX.rstrip('/'),
    'expanded_files':expanded,'visibility_unchanged':True,'default_branch_unchanged':True,
    'original_worktree_touched':False,'publication_GPU_used':False,'task_GPU_forwards':64,
    'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
(STAGE/'PUBLICATION_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
remember('stage','PUBLISHED_AWAITING_ANONYMOUS_READBACK')
print(json.dumps(receipt))
