"""Bounded one-sequence MVS acquisition from pinned mirror, no full dataset."""
import argparse,concurrent.futures,hashlib,json,os,pathlib,urllib.request,time,threading
ROOT=pathlib.Path(__file__).resolve().parents[2]
REV='c886d86505054f18f79d0a1c838150d9e98935b2'
DEST=ROOT/'inputs/MVS-Synth'
def request(url):
 return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'GameCam-VO-R2.1-bounded-pilot'}),timeout=45)
def digest(b):return hashlib.sha256(b).hexdigest()
def main():
 assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
 p=argparse.ArgumentParser();p.add_argument('--scope',choices=['pilot','complete'],required=True);a=p.parse_args()
 tree=json.loads((ROOT/'03_gt_admission/MIRROR_SEQUENCE_0001_TREE.json').read_text())
 files=[x for x in tree if x['type']=='file']
 assert len(files)==300 and sum(x['size'] for x in files)==85484738
 if a.scope=='pilot':files=[x for x in files if pathlib.PurePosixPath(x['path']).stem in ['0000','0049','0099']]
 log=ROOT/('03_gt_admission/SECOND_SEQUENCE_'+a.scope.upper()+'_ACQUISITION.json')
 if log.exists():raise RuntimeError('Acquisition log already exists')
 total=0;lock=threading.Lock();started=time.perf_counter()
 def one(row):
  nonlocal total
  path=pathlib.PurePosixPath(row['path'])
  assert path.parts[:2]==('GTAV_540','0001') and '..' not in path.parts
  dst=DEST/path
  existed=dst.is_file()
  if existed:b=dst.read_bytes()
  else:
   url='https://huggingface.co/datasets/fantasticoven/mvs-synth/resolve/'+REV+'/'+row['path']
   with request(url) as response:b=response.read(row['size']+1)
   with lock:total+=len(b)
  if len(b)!=row['size']:raise RuntimeError('Size mismatch '+str(path))
  if 'lfs' in row:
   if digest(b)!=row['lfs']['oid']:raise RuntimeError('LFS SHA mismatch '+str(path))
   kind='SHA256_LFS'
  else:
   got=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
   if got!=row['oid']:raise RuntimeError('Git blob mismatch '+str(path))
   kind='GIT_BLOB_SHA1'
  if not existed:
   dst.parent.mkdir(parents=True,exist_ok=True)
   with dst.open('xb') as f:f.write(b)
  return {'path':str(dst),'source_path':row['path'],'bytes':len(b),'sha256':digest(b),'source_identity':kind,'reused':existed}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  rows=list(pool.map(one,files))
 result={'repository':'fantasticoven/mvs-synth','revision':REV,'scope':a.scope,'files':rows,
         'network_payload_bytes':total,'dataset_sequence_total_bytes':85484738,'seconds':time.perf_counter()-started,
         'new_dataset_bytes_under_100MiB':total<100*1024**2,'complete_sequence':len(files)==300,
         'official_archive_all_member_crosscheck':False,'GT_metric_unit_established':False}
 with log.open('x',encoding='utf-8') as f:f.write(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k!='files'}))
if __name__=='__main__':main()
