"""Publish this CPU review through the previously authorized server wrapper.

No credential is read into the local process or copied from the server. No
GPU/model service is queried or changed. No repository visibility/default-branch
change, force-push, history deletion, or research computation is performed.
"""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
from urllib.request import Request,urlopen
from urllib.parse import urlencode,urlsplit
import zipfile

from common import PARENT,REVIEW,ROOT,TASK,dump,sha

PRIVATE = TASK/'private/publication'
REPO = 'Pseven0108/GameCam-VO'
PIN = 'SHA256:u1vPsq3oZJFNIp4O3T2wFQLTXqBDLRhR8QmjJ9cw4VA'
KNOWN = Path('D:/aaa/GameCam-VO/experiments/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/evidence/sc01-30723.known_hosts')
KEY = Path.home()/'.ssh/id_ed25519_rivermind_codex'
SSH = Path(os.environ['WINDIR'])/'System32/OpenSSH/ssh.exe'
WRAPPER = '/usr/local/bin/gamecam-gh'


def command(code):
    identity = subprocess.check_output([str(SSH.with_name('ssh-keygen.exe')),'-lf',str(KNOWN),'-E','sha256'],text=True)
    if PIN not in identity:
        raise RuntimeError('Previously trusted host-key file no longer matches the user-confirmed pin')
    settings = dict(BatchMode='yes',IdentitiesOnly='yes',StrictHostKeyChecking='yes',
        UserKnownHostsFile=str(KNOWN),GlobalKnownHostsFile='none',
        HostKeyAlias='[sc01-ssh.gpuhome.cc]:30723',HostKeyAlgorithms='ssh-ed25519',
        UpdateHostKeys='no',ForwardAgent='no',ForwardX11='no',
        ConnectionAttempts='1',ConnectTimeout='10',ServerAliveInterval='30',ServerAliveCountMax='3')
    return [str(SSH),'-T','-p','31454','-F','none','-i',str(KEY),
            *[item for k,v in settings.items() for item in ('-o',k+'='+v)],
            'root@sc01-ssh.gpuhome.cc','exec /usr/bin/python3 -B -u -c '+shlex.quote(code)]


def remote(code,data,timeout=240):
    result = subprocess.run(command(code),input=data,capture_output=True,timeout=timeout,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        # Do not echo arbitrary credential-bearing child diagnostics.
        raise RuntimeError('Scoped server publication operation failed, exit '+str(result.returncode))
    return json.loads(result.stdout)


def api(method,path='',value=None):
    if path and not path.startswith(('/','?')):
        raise ValueError('Unexpected repository-relative API path')
    payload = dict(endpoint='repos/'+REPO+path,method=method,value=value)
    code = '''import json,subprocess,sys
x=json.load(sys.stdin)
args=[WRAPPER,'api',x['endpoint'],'--method',x['method']]
body=None
if x['value'] is not None:
 args+=['--input','-'];body=json.dumps(x['value']).encode()
p=subprocess.run(args,input=body,capture_output=True,timeout=180)
if p.returncode: raise RuntimeError('Scoped GitHub API failed, exit '+str(p.returncode))
sys.stdout.buffer.write(p.stdout)
'''.replace('WRAPPER',repr(WRAPPER))
    return remote(code,json.dumps(payload).encode())


def stream(path,code,timeout=900):
    p = subprocess.Popen(command(code),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        with Path(path).open('rb') as f:
            for block in iter(lambda:f.read(1024**2),b''):
                p.stdin.write(block)
        p.stdin.close();p.stdin=None
        output,error=p.communicate(timeout=timeout)
    except BaseException:
        if p.poll() is None:p.terminate()
        raise
    if p.returncode:
        raise RuntimeError('Server publication transfer failed; partial state retained, exit '+str(p.returncode))
    return json.loads(output)


def git(*args,input=None):
    p = subprocess.run(['git',*args],cwd=ROOT,input=input,capture_output=True)
    if p.returncode:
        raise RuntimeError('Local Git operation failed: '+args[0])
    return p.stdout.decode().strip()


def push(commit,manifest):
    bundle = PRIVATE/'task011d-publication.bundle'
    if not bundle.exists():
        git('bundle','create',str(bundle),'HEAD','^'+manifest['parent_sha'])
    git('bundle','verify',str(bundle))
    expected = dict(commit=commit,parent=manifest['parent_sha'],branch=manifest['branch'],
                    bytes=bundle.stat().st_size,sha256=sha(bundle))
    code = '''import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
x=EXPECTED
root=Path('/dev/shm')/('gamecam-task011d-publication-'+x['commit'][:12])
assert not root.exists(),'Preserve uncertain publication staging'
assert shutil.disk_usage('/dev/shm').free>=2*x['bytes']+32*1024**2
root.mkdir(mode=0o700)
(root/'OWNER.json').write_text(json.dumps(x))
bundle=root/'review.bundle';h=hashlib.sha256();n=0
with bundle.open('xb') as f:
 for b in iter(lambda:sys.stdin.buffer.read(1024**2),b''):
  h.update(b);f.write(b);n+=len(b)
assert n==x['bytes'] and h.hexdigest()==x['sha256']
env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never',TMPDIR=str(root))
for k in ('GIT_TRACE','GIT_TRACE_CURL','GIT_CURL_VERBOSE','GIT_TRACE_PACKET'):env.pop(k,None)
base=['git','-c','credential.helper=','-c','credential.helper=!WRAPPER auth git-credential','-c','credential.useHttpPath=true']
def run(args):
 p=subprocess.run(args,capture_output=True,env=env,timeout=600)
 if p.returncode:raise RuntimeError('Scoped Git operation failed, exit '+str(p.returncode))
 return p.stdout.decode().strip()
repo=root/'git';run(base+['init','--bare',str(repo)])
g=base+['--git-dir',str(repo)]
run(g+['remote','add','origin','https://github.com/REPO.git'])
before=run(g+['ls-remote','origin','refs/heads/'+x['branch']])
assert not before or before.split()[0]==x['commit'],'Preserve a different existing branch'
run(g+['fetch','--filter=blob:none','--depth=1','origin',x['parent']])
run(g+['bundle','unbundle',str(bundle)])
run(g+['push','--porcelain','origin',x['commit']+':refs/heads/'+x['branch']])
after=run(g+['ls-remote','origin','refs/heads/'+x['branch']]);assert after.split()[0]==x['commit']
assert root.resolve().parent==Path('/dev/shm') and json.loads((root/'OWNER.json').read_text())==x
shutil.rmtree(root)
print(json.dumps(dict(status='PUSHED',**x,credential_exported=False,force_push=False,
                     own_tmpfs_staging_removed=True,research_models_or_GPU_invoked=False)))
'''.replace('EXPECTED',repr(expected)).replace('WRAPPER',WRAPPER).replace('REPO',REPO)
    return stream(bundle,code)


def upload(path,release):
    address = release['upload_url'].split('{')[0]+'?'+urlencode({'name':path.name})
    if urlsplit(address).hostname!='uploads.github.com':
        raise RuntimeError('Unexpected upload host')
    expected = dict(bytes=path.stat().st_size,sha256=sha(path),address=address)
    code = '''import hashlib,json,os,subprocess,sys
x=EXPECTED
fd=os.memfd_create('gamecam-task011d-review',flags=0);h=hashlib.sha256();n=0
with os.fdopen(os.dup(fd),'wb') as f:
 for b in iter(lambda:sys.stdin.buffer.read(1024**2),b''):
  f.write(b);h.update(b);n+=len(b)
assert n==x['bytes'] and h.hexdigest()==x['sha256']
os.lseek(fd,0,os.SEEK_SET)
p=subprocess.run([WRAPPER,'api',x['address'],'--method','POST','--input','/proc/self/fd/'+str(fd),
 '-H','Content-Type: application/octet-stream','-H','Content-Length: '+str(n)],
 capture_output=True,pass_fds=(fd,),timeout=600)
os.close(fd)
if p.returncode:raise RuntimeError('Scoped release upload failed')
a=json.loads(p.stdout)
assert a['size']==n and a['digest']=='sha256:'+x['sha256'] and a['state']=='uploaded'
print(json.dumps(a))
'''.replace('EXPECTED',repr(expected)).replace('WRAPPER',repr(WRAPPER))
    return stream(path,code)


def main():
    manifest = json.loads((PRIVATE/'allowlist.json').read_text())
    receipt_path = PRIVATE/'PUBLICATION_RECEIPT.json'
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    metadata = api('GET','?verify='+str(time.time_ns()))
    if metadata['id']!=1450634998 or metadata['private'] or metadata['full_name'].lower()!=REPO.lower():
        raise RuntimeError('Repository identity/public visibility changed; do not change it')
    receipt.setdefault('original_default_branch',metadata['default_branch'])
    receipt.update(visibility_changed=False,default_branch_changed=False,server_credential_exported=False)
    if 'commit' not in receipt:
        if git('rev-parse','HEAD')!=PARENT or git('diff','--cached','--name-only'):
            raise RuntimeError('Preserve unexpected branch or staged edits')
        if git('branch','--show-current')!=manifest['branch']:
            raise RuntimeError('Unexpected local TASK011D branch')
        for row in manifest['entries']:
            if sha(row['source'])!=row['sha256']:
                raise RuntimeError('Publication allowlist changed')
        paths = PRIVATE/'paths.nul'
        paths.write_bytes(b''.join(r['path'].encode()+b'\0' for r in manifest['entries']))
        git('--literal-pathspecs','add','--sparse','-f','--pathspec-from-file='+str(paths),'--pathspec-file-nul')
        staged = set(git('diff','--cached','--name-only').splitlines())
        if staged != {r['path'] for r in manifest['entries']}:
            raise RuntimeError('Staged path set differs from current-stage explicit allowlist')
        message = PRIVATE/'COMMIT_MESSAGE.txt'
        message.write_text('TASK011D: source-only A7 GPU adapter and Route A dual-validation preparation\n\n169 tests pass; 1216 RGB audited; no formal SLAM or native BA.\n',encoding='utf-8')
        git('commit','-F',str(message))
        receipt.update(status='COMMITTED_NOT_PUSHED',commit=git('rev-parse','HEAD'),
                       tree=git('rev-parse','HEAD^{tree}'),parent=PARENT,branch=manifest['branch'])
        dump(receipt_path,receipt)
    if receipt['status']=='COMMITTED_NOT_PUSHED':
        print('PUBLISHING_EXPANDED_CPU_REVIEW',receipt['commit'],flush=True)
        proof = push(receipt['commit'],manifest)
        dump(PRIVATE/'SERVER_PUSH_RECEIPT.json',proof)
        receipt['status']='PUSHED';dump(receipt_path,receipt)
    commit = receipt['commit']
    tree = api('GET','/git/trees/'+receipt['tree']+'?recursive=1&verify='+str(time.time_ns()))
    if tree.get('truncated'):raise RuntimeError('Remote tree response truncated')
    blobs = {r['path']:r['sha'] for r in tree['tree'] if r['type']=='blob'}
    if any(blobs.get(r['path'])!=r['git_blob_sha'] for r in manifest['entries']):
        raise RuntimeError('Published expanded blob identity mismatch')
    raw = 'https://raw.githubusercontent.com/'+REPO+'/'+commit+'/'+manifest['review_directory']+'/FINAL_REVIEW.md'
    with urlopen(Request(raw,headers={'User-Agent':'GameCam-VO-Public-Verification'}),timeout=45) as response:
        if response.read()!=(REVIEW/'FINAL_REVIEW.md').read_bytes():
            raise RuntimeError('Anonymous public final report differs')
    receipt['public_expanded_blob_identities_verified']=len(manifest['entries'])
    dump(receipt_path,receipt)
    if 'release_id' not in receipt:
        release = api('POST','/releases',dict(tag_name=manifest['release_tag'],target_commitish=commit,
            name='TASK011D — A7 GPU Adapter and dual-validation preparation',draft=True,prerelease=True,
            make_latest='false',body='Preparation passed; local synthetic CUDA only. No formal SLAM results. Full evidence upload in progress.'))
        receipt['release_id']=release['id'];dump(receipt_path,receipt)
    else:
        release = api('GET','/releases/'+str(receipt['release_id']))
    paths = [Path(manifest['archive']),Path(manifest['archive']+'.sha256')]
    assets = api('GET','/releases/'+str(receipt['release_id'])+'/assets?per_page=100')
    for path in paths:
        old = next((a for a in assets if a['name']==path.name),None)
        if old:
            if old['size']!=path.stat().st_size or old['digest']!='sha256:'+sha(path):
                raise RuntimeError('Preserve mismatching existing release asset')
        else:
            upload(path,release)
    body = f'''TASK011D preparation complete: source-only A7 GPU adapter, 19 Route A windows, separate fixed-state and end-to-end frameworks.

**169/169 tests passed. 1216 JPEGs fully decoded/CRC-verified.** Local RTX5060 synthetic CUDA only; remote frozen PyTorch2.1 CPU API compatibility checked without CUDA initialization. No model inference, native BA, pilot or formal SLAM runs.

285 future E2E jobs and the fixed-state protocol are frozen for review. Historical full-sequence baseline exposure is explicitly marked; TASK011B sources and val_014 are excluded. Secondary degradation margins remain proposals awaiting approval.

- [Fixed-commit final review](https://github.com/{REPO}/blob/{commit}/{manifest['review_directory']}/FINAL_REVIEW.md)
- [Complete expanded evidence](https://github.com/{REPO}/tree/{commit}/{manifest['review_directory']})
- [ZIP SHA256](https://github.com/{REPO}/blob/{commit}/review_packages/{paths[1].name})

Full ZIP includes source, all final and development test logs, profiler traces, transfer/performance evidence, data admission metadata, configuration/implementation hashes and both experiment protocols. Raw RGB/GT, weights, environments and native binaries are excluded. Original evidence stays local.

This is engineering/data readiness, not evidence that A5 beats A7. Formal GPU execution requires separate approval. No production baseline or sealed B/C release changed.
'''
    if release['draft']:
        api('PATCH','/releases/'+str(receipt['release_id']),dict(draft=False,prerelease=True,make_latest='false',body=body))
    public = api('GET','/releases/tags/'+manifest['release_tag']+'?verify='+str(time.time_ns()))
    ref = api('GET','/git/ref/tags/'+manifest['release_tag'])
    if public['draft'] or ref['object']['sha']!=commit or len(public['assets'])!=2:
        raise RuntimeError('Release/tag binding verification failed')
    asset = next(a for a in public['assets'] if a['name']==paths[0].name)
    if asset['digest']!='sha256:'+manifest['archive_sha256']:
        raise RuntimeError('GitHub ZIP digest mismatch')
    verify = PRIVATE/'PUBLIC_ZIP_VERIFICATION.zip'
    if verify.exists():raise RuntimeError('Preserve previous incomplete public verification download')
    print('VERIFYING_ANONYMOUS_PUBLIC_COMPLETE_ZIP',asset['size'],flush=True)
    with urlopen(Request(asset['browser_download_url'],headers={'User-Agent':'GameCam-VO-Public-Verification'}),timeout=90) as response, verify.open('xb') as stream:
        for block in iter(lambda:response.read(1024**2),b''):stream.write(block)
    if sha(verify)!=manifest['archive_sha256'] or verify.stat().st_size!=asset['size']:
        raise RuntimeError('Anonymous public download identity mismatch')
    with zipfile.ZipFile(verify) as z:
        if z.testzip() is not None:raise RuntimeError('Public ZIP CRC failure')
        records = list(csv.DictReader(io.StringIO(z.read('SHA256_MANIFEST.csv').decode())))
        if len(records)!=manifest['internal_sha256_count']:raise RuntimeError('Public file count mismatch')
        for row in records:
            b = z.read(row['path'])
            if len(b)!=int(row['bytes']) or hashlib.sha256(b).hexdigest()!=row['sha256']:
                raise RuntimeError('Public ZIP internal SHA mismatch')
    after = api('GET','?verify='+str(time.time_ns()))
    if after['private'] or after['default_branch']!=receipt['original_default_branch']:
        raise RuntimeError('Repository visibility/default branch drifted')
    receipt.update(status='PUBLIC_VERIFIED',zip_sha256=sha(verify),zip_bytes=verify.stat().st_size,
        ZIP_CRC='PASS',internal_sha256_verified=len(records),release_url=public['html_url'],
        zip_public_url=asset['browser_download_url'],anonymous_public_download=True,
        formal_SLAM_runs=0,models_loaded=0,formal_SLAM_GPU_started=False,synthetic_CUDA_executed=True)
    dump(receipt_path,receipt)
    # User's standing cleanup: only this delivered complete review ZIP, after
    # public integrity verification. Expanded code/reports/evidence stay intact.
    if paths[0].resolve().parent!=(ROOT/'review_packages').resolve() or sha(paths[0])!=receipt['zip_sha256']:
        raise RuntimeError('Current-delivery archive cleanup identity check failed')
    paths[0].unlink()
    verify.unlink()
    bundle = PRIVATE/'task011d-publication.bundle'
    if bundle.is_file():bundle.unlink()
    receipt['current_local_complete_review_ZIP_removed']=True
    receipt['expanded_reports_and_original_evidence_retained']=True
    dump(receipt_path,receipt)
    print(json.dumps(receipt,indent=2),flush=True)


if __name__ == '__main__':
    main()
