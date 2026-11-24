from transport import *
import shutil
meta=json.loads((ROOT/'evidence/RAW_ARCHIVE_STATUS.json').read_text(encoding='utf8'));assert meta['phase']=='complete' and meta['exit_code']==0
folder=ROOT/'artifacts';folder.mkdir(exist_ok=True);dest=folder/'TASK004C_FIXED_STATE_RAW_EVIDENCE.zip';part=folder/'TASK004C_FIXED_STATE_RAW_EVIDENCE.zip.partial';assert not dest.exists() and not part.exists()
assert shutil.disk_usage(ROOT).free>=meta['archive_bytes']+1024**3,'LOCAL_STORAGE_BLOCKED'
args=ssh_base(PRE)+['-o','ClearAllForwardings=yes',HOST,'exec cat -- '+shlex.quote(meta['archive'])];err=ROOT/'evidence/RAW_DOWNLOAD.ssh.stderr.txt';start=time.monotonic();h=hashlib.sha256();size=0;shown=0
with err.open('xb') as se,part.open('xb') as f:
 p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=se,creationflags=CREATE)
 while True:
  b=p.stdout.read(4*1024**2)
  if not b:break
  f.write(b);h.update(b);size+=len(b)
  assert size<=meta['archive_bytes'],'unexpected length'
  if size-shown>=128*1024**2:print(json.dumps({'downloaded_bytes':size,'total_bytes':meta['archive_bytes'],'elapsed_seconds':time.monotonic()-start}),flush=True);shown=size
 ec=p.wait(timeout=30)
trust=verified(err);report=dict(exit_code=ec,bytes=size,expected_bytes=meta['archive_bytes'],sha256=h.hexdigest(),expected_sha256=meta['archive_sha256'],elapsed_seconds=time.monotonic()-start,trust=trust,local_path=str(dest),source_path=meta['archive'],sha256_match=h.hexdigest()==meta['archive_sha256'],new_gpu_work=False)
(ROOT/'evidence/RAW_DOWNLOAD_RECEIPT.json').write_text(json.dumps(report,indent=2),encoding='utf8')
assert ec==0 and size==meta['archive_bytes'] and report['sha256_match'] and all(trust.values())
part.rename(dest);print(json.dumps(report,indent=2))
