"""Publish through the existing server-only GitHub credential wrapper.

Credentials never leave the server. Git objects use a bounded private tmpfs
directory only AFTER the formal batch; the completed review ZIP streams through
stdin and is never duplicated on the server's space-constrained data disk.
No global Git/SSH/proxy settings are changed.
"""
import hashlib,json,os,shlex,subprocess
from pathlib import Path
from common import ROOT,TASK,dump,sha
from remote_transport import SSH,options

WRAPPER='/usr/local/bin/gamecam-gh'
REPO='Pseven0108/GameCam-VO'


def command(code):
    return [str(SSH),'-T','-p','31454',*options(),'root@sc01-ssh.gpuhome.cc',
            'exec /usr/bin/python3 -B -u -c '+shlex.quote(code)]


def request(method,path,value=None):
    if path and not path.startswith(('/','?')):raise ValueError('Unexpected repository-relative API path')
    endpoint='repos/'+REPO+path
    code='''import json,subprocess,sys
payload=json.load(sys.stdin)
args=[WRAPPER,'api',payload['endpoint'],'--method',payload['method']]
body=None
if payload['value'] is not None:
 args+=['--input','-'];body=json.dumps(payload['value']).encode()
p=subprocess.run(args,input=body,capture_output=True,timeout=180)
if p.returncode:
 print(json.dumps(dict(server_wrapper_exit=p.returncode,method=payload['method'])))
 sys.exit(1)
sys.stdout.buffer.write(p.stdout)
'''.replace('WRAPPER',repr(WRAPPER))
    p=subprocess.run(command(code),input=json.dumps(dict(endpoint=endpoint,method=method,value=value)).encode(),
                     capture_output=True,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW)
    if p.returncode:raise RuntimeError('Server-scoped GitHub API failed: '+method+' '+path.split('?')[0])
    return json.loads(p.stdout) if p.stdout else None


def stream_file(path,code,timeout=1800):
    """No token appears in argv, local files, stdout or SSH transport."""
    p=subprocess.Popen(command(code),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    sent=0;notice=64*1024**2
    try:
        with Path(path).open('rb') as f:
            for block in iter(lambda:f.read(1024**2),b''):
                p.stdin.write(block);sent+=len(block)
                if sent>=notice:
                    print('SERVER_PUBLICATION_STREAM_BYTES',sent,flush=True);notice+=64*1024**2
        p.stdin.close();p.stdin=None
        out,error=p.communicate(timeout=timeout)
    except BaseException:
        # Do not print arbitrary diagnostics from any credential-bearing child.
        if p.poll() is None:p.terminate()
        raise
    if p.returncode:raise RuntimeError('Server publication stage failed; partial assets preserved, credentials not logged')
    return json.loads(out)


def push(commit,parent,branch):
    if not (TASK/'gpu_results/BATCH_COMPLETE.json').exists():
        raise RuntimeError('Publication tmpfs staging is only permitted after the GPU batch')
    private=TASK/'private/publication';ref='refs/codex-delivery/task011b-20261127'
    def git(*args):
        p=subprocess.run(['git',*args],cwd=ROOT,capture_output=True)
        if p.returncode:raise RuntimeError('Local publication bundle operation failed')
        return p.stdout.decode().strip()
    old=subprocess.run(['git','rev-parse','--verify',ref],cwd=ROOT,capture_output=True,text=True)
    if old.returncode==0 and old.stdout.strip()!=commit:raise RuntimeError('Preserve different local delivery ref')
    if old.returncode:git('update-ref',ref,commit)
    bundle=private/'task011b-publication.bundle'
    if not bundle.exists():git('bundle','create',str(bundle),ref,'^'+parent)
    git('bundle','verify',str(bundle))
    expected=dict(commit=commit,parent=parent,branch=branch,bundle_bytes=bundle.stat().st_size,bundle_sha256=sha(bundle))
    code='''import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
x=EXPECTED
root=Path('/dev/shm')/('gamecam-task011b-publication-'+x['commit'][:12])
assert not root.exists(),'Preserve earlier uncertain publication state'
assert shutil.disk_usage('/dev/shm').free>=2*x['bundle_bytes']+1024**3,'Insufficient private publication tmpfs budget'
root.mkdir(mode=0o700)
(root/'OWNER.json').write_text(json.dumps(x))
bundle=root/'review.bundle';h=hashlib.sha256();n=0
with bundle.open('xb') as f:
 for block in iter(lambda:sys.stdin.buffer.read(1024**2),b''):
  f.write(block);h.update(block);n+=len(block)
assert n==x['bundle_bytes'] and h.hexdigest()==x['bundle_sha256']
env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never',TMPDIR=str(root))
for name in ('GIT_TRACE','GIT_TRACE_CURL','GIT_CURL_VERBOSE','GIT_TRACE_PACKET'):
 env.pop(name,None)
repo=root/'git'
base=['git','-c','credential.helper=','-c','credential.helper=!WRAPPER auth git-credential',
      '-c','credential.useHttpPath=true']
def run(args):
 p=subprocess.run(args,capture_output=True,env=env,timeout=900)
 if p.returncode:raise RuntimeError('Publication Git operation failed, exit '+str(p.returncode))
 return p.stdout.decode().strip()
run(base+['init','--bare',str(repo)])
g=base+['--git-dir',str(repo)]
url='https://github.com/REPO.git'
run(g+['remote','add','origin',url])
run(g+['fetch','--filter=blob:none','--depth=1','origin',x['parent']])
run(g+['bundle','unbundle',str(bundle)])
run(g+['push','--porcelain','origin',x['commit']+':refs/heads/'+x['branch']])
visible=run(g+['ls-remote','origin','refs/heads/'+x['branch']])
assert visible.split()[0]==x['commit']
journal=Path('/root/rivermind-data/GAMECAM_TASK011B_PUBLICATION_20261127')
journal.mkdir(mode=0o700,exist_ok=True)
proof=dict(status='EXPANDED_REVIEW_COMMIT_PUSHED',**x,server_only_wrapper=True,
           credential_exported=False,global_configuration_changed=False,
           tmpfs_bytes_budget=2*x['bundle_bytes']+1024**3)
(journal/('git-push-'+x['commit'][:12]+'.json')).write_text(json.dumps(proof,indent=2))
assert root.resolve().parent==Path('/dev/shm') and json.loads((root/'OWNER.json').read_text())==x
shutil.rmtree(root)
proof['own_tmpfs_publication_directory_removed']=True
print(json.dumps(proof))
'''.replace('EXPECTED',repr(expected)).replace('WRAPPER',WRAPPER).replace('REPO',REPO)
    result=stream_file(bundle,code)
    dump(private/'SERVER_GIT_PUSH_RECEIPT.json',result)
    return result


def upload(path,release):
    from urllib.parse import urlencode,urlsplit
    address=release['upload_url'].split('{')[0]+'?'+urlencode({'name':path.name})
    if urlsplit(address).hostname!='uploads.github.com':raise RuntimeError('Unexpected upload origin')
    code='''import hashlib,json,subprocess,sys
raw=sys.stdin.buffer.read()
assert len(raw)==SIZE and hashlib.sha256(raw).hexdigest()==IDENTITY
args=[WRAPPER,'api',ADDRESS,'--method','POST','--input','-',
      '-H','Content-Type: application/octet-stream']
p=subprocess.run(args,input=raw,capture_output=True,timeout=1800)
if p.returncode:raise RuntimeError('Server-wrapper asset upload failed')
x=json.loads(p.stdout)
assert x['size']==len(raw) and x['digest']=='sha256:'+IDENTITY and x['state']=='uploaded'
print(json.dumps(x))
'''.replace('SIZE',str(path.stat().st_size)).replace('IDENTITY',repr(sha(path)))
    code=code.replace('WRAPPER',repr(WRAPPER)).replace('ADDRESS',repr(address))
    return stream_file(path,code,timeout=2400)
