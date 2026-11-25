"""Download an owned immutable task artifact, verify tar CRC/hash and retain locally."""
import sys,pathlib,json,subprocess,hashlib,tarfile,time,os
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'01_runtime'));from ssh_execute import ssh,base
RECEIVER=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-GPU-20261125-R1')
a=sys.argv[1];kind=sys.argv[2] if len(sys.argv)>2 else 'snapshot'
partial=len(sys.argv)>3 and sys.argv[3]=='--partial'
assert not partial or kind=='result'
assert a in [x+'_RGB'+str(r).zfill(3) for x in ['D1_S1','D0_S1','D1_S0','D0_S0'] for r in [19,233,401]]
assert kind in ('snapshot','result')
remote='/root/rivermind-data/GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1/'+('snapshots' if kind=='snapshot' else 'results_context02')+'/'+a
prefix='partial' if partial else kind
out=RECEIVER/(prefix+'_'+a+'.tar');err=ROOT/'00_intake'/('COLLECT_'+prefix+'_'+a+'.stderr.txt');start=time.time()
cmd='tar -C '+remote+' -cf - .'
with out.open('xb') as f,err.open('xb') as e:p=subprocess.run(base()+['-o','ClearAllForwardings=yes',ssh.HOST,cmd],stdout=f,stderr=e,timeout=900,creationflags=ssh.CREATE)
if p.returncode!=0 or not all(ssh.verified(err).values()):raise RuntimeError('Trusted archive transfer failed')
archive_sha=hashlib.sha256();
with out.open('rb') as f:
 for b in iter(lambda:f.read(8*1024**2),b''):archive_sha.update(b)
member_hashes={};manifest=None
with tarfile.open(out,'r:') as t:
 for m in t:
  if not m.isfile():continue
  n=m.name.removeprefix('./');assert not n.startswith('/') and '..' not in pathlib.PurePosixPath(n).parts
  h=hashlib.sha256();raw=b''
  with t.extractfile(m) as f:
   for b in iter(lambda:f.read(8*1024**2),b''):h.update(b);raw=raw+b if n=='manifest.json' else b''
  member_hashes[n]={'bytes':m.size,'sha256':h.hexdigest()}
  if n=='manifest.json':manifest=json.loads(raw)
if manifest:
 for n,x in manifest['files'].items():assert member_hashes[n]==x,(n,member_hashes[n],x)
receipt={'archive':str(out),'archive_bytes':out.stat().st_size,'archive_sha256':archive_sha.hexdigest(),'kind':kind,'partial_terminal_evidence':partial,'state':a,'members':member_hashes,'all_internal_storage_SHA_verified':manifest is not None,'remote_source':remote,'transfer_seconds':time.time()-start,'SSH_trust':ssh.verified(err),'source_removed':False}
with (RECEIVER/(prefix+'_'+a+'.VERIFIED.json')).open('x') as f:json.dump(receipt,f,indent=2)
print(json.dumps({k:v for k,v in receipt.items() if k!='members'}))
