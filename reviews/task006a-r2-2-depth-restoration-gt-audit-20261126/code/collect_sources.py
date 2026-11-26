"""Bounded primary-source metadata/code retrieval, never dataset downloads."""
import datetime,json,shutil,urllib.request
from common import *

def get(url,path):
    req=urllib.request.Request(url,headers={'User-Agent':'GameCam-VO-R2.2-source-audit','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=35) as r:
        data=r.read(3_000_001)
        if len(data)>3_000_000: raise RuntimeError('Source/metadata size limit')
        info={'url':url,'status':r.status,'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'bytes':len(data),'headers':{k:v for k,v in r.headers.items() if k.lower() in ['etag','last-modified','content-type']}}
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:f.write(data)
    return {**info,'path':str(path.relative_to(ROOT)),'sha256':sha(path)}

def main():
    cpu_only();rows=[]
    for old,name in [
        (PREV/'evidence/Metric3D-eb5b6fac/hubconf.py','Metric3D-eb5b6fac/hubconf.py'),
        (PREV/'evidence/Metric3D-eb5b6fac/DROID-W-runtime/metric_depth_estimators.py','DROID-W-runtime/metric_depth_estimators.py'),
        (R2/'evidence/MVS_PROVENANCE/generate_volume_train.py','DeepMVS/generate_volume_train.py'),
        (R2/'evidence/MVS_PROVENANCE/DeepMVS_README.md','DeepMVS/README.historical.md')]:
        new=ROOT/'01_sources'/name;new.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(old,new)
        rows.append({'kind':'SEALED_SOURCE_COPY','source':str(old),'path':str(new.relative_to(ROOT)),'sha256':sha(new)})
    urls=[
      ('https://raw.githubusercontent.com/YvanYin/Metric3D/eb5b6fac0dc155e4e52f576e304fbf11655ff339/hubconf.py','Metric3D-eb5b6fac/hubconf.fresh.py'),
      ('https://api.github.com/repos/phuang17/DeepMVS/issues/25','DeepMVS/issue25.json'),
      ('https://api.github.com/repos/phuang17/DeepMVS/issues/25/comments?per_page=100','DeepMVS/issue25.comments.json'),
      ('https://api.github.com/repos/phuang17/DeepMVS/issues/13/comments?per_page=100','DeepMVS/issue13.comments.json'),
      ('https://api.github.com/repos/phuang17/DeepMVS/issues/16/comments?per_page=100','DeepMVS/issue16.comments.json'),
      ('https://phuang17.github.io/DeepMVS/index.html','DeepMVS/project_page.html'),
      ('https://raw.githubusercontent.com/pytorch/pytorch/v2.1.0/aten/src/ATen/native/UpSampleBilinear2d.cpp','PyTorch-v2.1.0/UpSampleBilinear2d.cpp'),
      ('https://raw.githubusercontent.com/pytorch/pytorch/v2.1.0/aten/src/ATen/native/UpSample.h','PyTorch-v2.1.0/UpSample.h')]
    for url,name in urls:
        try: rows.append(get(url,ROOT/'01_sources'/name))
        except Exception as e: rows.append({'url':url,'error':repr(e),'status':'UNAVAILABLE'})
    live=ROOT/'01_sources/Metric3D-eb5b6fac/hubconf.fresh.py'
    if live.exists() and sha(live)!=sha(ROOT/'01_sources/Metric3D-eb5b6fac/hubconf.py'): raise RuntimeError('Pinned source copy mismatch')
    dump(ROOT/'01_sources/SOURCE_RETRIEVAL_MANIFEST.json',{'sources':rows,'dataset_bytes_downloaded':0})
    excerpts=[]
    for p in (ROOT/'01_sources/DeepMVS').glob('*.json'):
        obj=json.loads(p.read_text('utf-8'));items=obj if isinstance(obj,list) else [obj]
        for x in items: excerpts.append({'source_file':p.name,'url':x.get('html_url'),'author':x.get('user',{}).get('login'),
                  'association':x.get('author_association'),'body':x.get('body'),'created_at':x.get('created_at'),'updated_at':x.get('updated_at')})
    dump(ROOT/'01_sources/GT_AUTHOR_STATEMENTS.json',{'statements':excerpts})
    print(json.dumps({'source_requests':len(urls),'retrieved':sum(r.get('status')==200 for r in rows),'issues':[(x['url'],str(x['body'])[:420]) for x in excerpts if x['source_file'].startswith(('issue25','issue16'))]},ensure_ascii=False))

if __name__=='__main__': main()
