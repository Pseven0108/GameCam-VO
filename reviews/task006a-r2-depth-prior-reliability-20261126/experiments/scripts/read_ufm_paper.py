import hashlib,json,pathlib,sys,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/runtime_site'))
from pypdf import PdfReader
def main():
 cache=ROOT/'experiments/literature_cache';cache.mkdir(exist_ok=True)
 url='https://eems.mit.edu/wp-content/uploads/2022/03/2022_icra_ufm.pdf'
 path=cache/'ufm_icra2022.pdf'
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'GameCam-VO-research-audit'})
  with urllib.request.urlopen(req,timeout=25) as r:b=r.read(12*1024*1024+1)
  assert b.startswith(b'%PDF') and len(b)<=12*1024*1024
  with path.open('xb') as f:f.write(b)
  reader=PdfReader(path);pages=[p.extract_text() for p in reader.pages]
  (cache/'ufm_icra2022.extracted.txt').write_text('\n\n'.join(pages),encoding='utf-8')
  receipt={'source':url,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'pages':len(pages),'download':'PASS',
    'raw_pdf_and_extracted_full_text_excluded_from_GitHub':True}
  print('\n\n'.join(pages[2:6]))
 except Exception as e:
  receipt={'source':url,'download':'FAILED','reason':str(e),'full_method_experiments_audit_complete':False}
 (ROOT/'02_literature/UFM_FULLTEXT_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(receipt))
if __name__=='__main__':main()
