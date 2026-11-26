"""Bounded official TAR stream: compare sequence0001 members, never fetch whole dataset."""
import hashlib,json,os,pathlib,tarfile,time,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[2]
LIMIT=180000000 # Together with the 85,484,738-byte mirror sequence <256MiB.
URL='https://huggingface.co/datasets/phuang17/MVS-Synth/resolve/73e4b0abff2806a67c0f9bc038c3a1ac5df9ef0b/GTAV_540.tar.gz'
class BudgetExceeded(RuntimeError):pass
class Bounded:
 def __init__(self,raw):self.raw=raw;self.n=0
 def read(self,n=-1):
  left=LIMIT-self.n
  if left<=0:raise BudgetExceeded('Official compressed prefix budget reached')
  b=self.raw.read(min(left,n) if n>=0 else left);self.n+=len(b);return b
def main():
 assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
 start=time.perf_counter();rows=[];names=[];status='PARTIAL';error=None
 catalog=json.loads((ROOT/'03_gt_admission/MIRROR_SEQUENCE_0001_TREE.json').read_text())
 index={str(pathlib.PurePosixPath(x['path'])):x for x in catalog if x['type']=='file'}
 request=urllib.request.Request(URL,headers={'User-Agent':'GameCam-VO-bounded-GT-crosscheck','Accept-Encoding':'identity'})
 response=urllib.request.urlopen(request,timeout=45);reader=Bounded(response)
 headers={'content_length':response.headers.get('Content-Length'),'content_type':response.headers.get('Content-Type')}
 try:
  with tarfile.open(fileobj=reader,mode='r|gz') as stream:
   for member in stream:
    if len(names)<10:names.append(member.name)
    path=pathlib.PurePosixPath(member.name)
    parts=path.parts
    if not member.isfile() or '0001' not in parts:continue
    i=parts.index('0001');tail=parts[i:]
    if len(tail)!=3 or tail[1] not in ['images','depths','poses']:continue
    if member.size>8*1024**2:raise RuntimeError('Unexpected large member')
    data=stream.extractfile(member).read()
    local=ROOT/'inputs/MVS-Synth/GTAV_540'/pathlib.Path(*tail)
    h=hashlib.sha256(data).hexdigest()
    mirror=index.get('GTAV_540/'+'/'.join(tail))
    if mirror is None:raise RuntimeError('Official member not in pinned sequence catalog')
    identity_match=(h==mirror['lfs']['oid']) if 'lfs' in mirror else (hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==mirror['oid'])
    rows.append({'official_member':member.name,'local':str(local),'bytes':len(data),'sha256':h,
      'matches_mirror':len(data)==mirror['size'] and identity_match})
    if len(rows)%50==0:print('OFFICIAL_MATCHED_MEMBERS',len(rows),'NETWORK_BYTES',reader.n,flush=True)
    if len(rows)==300:status='ALL_300_TARGET_MEMBERS_READ';break
 except Exception as e:error=str(e);status='BOUNDED_PARTIAL' if isinstance(e,BudgetExceeded) else 'SOURCE_READ_INCOMPLETE'
 finally:response.close()
 result={'source':URL,'official_revision':'73e4b0abff2806a67c0f9bc038c3a1ac5df9ef0b','status':status,
         'bytes_read':reader.n,'hard_limit_bytes':LIMIT,'headers':headers,'initial_members':names,'target_files':rows,
         'matches':sum(x['matches_mirror'] for x in rows),'error':error,'seconds':time.perf_counter()-start,
         'full_archive_downloaded':False,'full_archive_CRC_certified':False,'target_member_bytes_compared':True}
 with (ROOT/'03_gt_admission/OFFICIAL_SEQUENCE_0001_CROSSCHECK.json').open('x',encoding='utf-8') as f:f.write(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k not in ['target_files','initial_members']}))
if __name__=='__main__':main()
