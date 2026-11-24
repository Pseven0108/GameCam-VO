"""Publish complete ZIP release and expanded immutable review, preserving old staged draft."""
import hashlib,json,os,pathlib,shutil,subprocess,sys,urllib.request,urllib.error,urllib.parse,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
OLD=pathlib.Path(r'D:\aaa\GameCam-VO\maintenance\GITHUB_AUTONOMOUS_PUBLICATION_20261124_R1\repository')
EXTERNAL_ROOT=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125')
REPO=EXTERNAL_ROOT/'publication_repository_r3'
sys.path.insert(0,r'D:\aaa\GameCam-VO\maintenance\GITHUB_REVIEW_PUBLICATION_20261124_R1')
from github_readonly import credential,api
SLUG='task004c-b-crossover-full-20261125';BRANCH='codex/'+SLUG;REL='reviews/'+SLUG;TAG=SLUG
ENV=dict(os.environ,GCM_INTERACTIVE='Never',GIT_TERMINAL_PROMPT='0',CUDA_VISIBLE_DEVICES='')
def cmd(args,timeout=180):
 q=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',env=ENV,timeout=timeout)
 if q.returncode:raise RuntimeError({'command_type':args[0],'exit_code':q.returncode,'stderr':q.stderr[-1000:]})
 return q.stdout.strip()
def git(*a,timeout=180):return cmd(['git','-C',str(REPO),*a],timeout)
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
def dump(name,x):(ROOT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
 package=json.loads((ROOT/'COMPLETED_PACKAGE_VALIDATION.json').read_text());assert package['ZIP_CRC']=='PASS' and package['manifest_all_match']
 token=credential();before=api('/repos/Pseven0108/GameCam-VO',token);assert before['private'] is False and before.get('permissions',{}).get('push')
 assert not REPO.exists(),'Reconcile existing publication; never overwrite'
 origin=cmd(['git','-C',str(OLD),'config','--get','remote.origin.url'])
 assert origin.startswith(('https://github.com/','git@github.com:')) and 'Pseven0108/GameCam-VO' in origin
 cmd(['git','clone','--shared','--no-checkout',str(OLD),str(REPO)])
 git('remote','set-url','origin',origin);git('fetch','origin',before['default_branch'])
 parent=git('rev-parse','FETCH_HEAD');git('checkout','-b',BRANCH,parent)
 assert not git('ls-remote','--heads','origin','refs/heads/'+BRANCH)
 target=REPO/REL;assert not target.exists();shutil.copytree(package['expanded_review'],target)
 zp=pathlib.Path(package.get('ZIP_path',str(ROOT/package['ZIP'])));assert sha(zp)==package['ZIP_sha256']
 release_url='https://github.com/Pseven0108/GameCam-VO/releases/download/'+TAG+'/'+package['ZIP']
 (target/'FULL_PACKAGE_DOWNLOAD.md').write_text('# Complete review archive\n\n[Download ZIP]('+release_url+')\n\nSHA-256: '+package['ZIP_sha256']+'\n\nBytes: '+str(package['ZIP_bytes'])+'\n\nExpanded reports and losslessly chunked logs are in this directory. Native recordings and excluded dataset/model payloads have inventories in PUBLICATION_EXCLUSIONS.json.\n',encoding='utf-8')
 status='# 当前状态 · Task004C-B 四组受控交叉实验\n\n**COMPLETE：B1、B2、B4、B3 均完成487帧、原生Final BA和完整Filler，退出码均为0。**\n\n- Common C0、INIT_D=0、val_007、seed43、stride=1。\n- S1和S0各包含D=1/D=0；离散调度固定，连续优化分别演化。\n- 早期失败现场保留，冻结优化公式、权重、R2 YAML及CUDA扩展未变。\n- 单序列单种子描述性机制实验，不等同于原始E0全流程或跨场景验证。\n- 原生Rerun记录保留，浏览器渲染未核实。用户已授权在归档发布核验后执行 shutdown；本提交封存时尚未执行，实际回执另行补充。\n\n[最终报告]('+REL+'/FINAL_REVIEW.md) · [完整ZIP]('+release_url+') · [展开证据]('+REL+') · [评价表]('+REL+'/evaluation/CROSSOVER_SUMMARY.csv)。\n'
 (REPO/'PROJECT_STATUS.md').write_text(status,encoding='utf-8')
 (REPO/'README.md').write_text('# GameCam-VO · 最新完整评审\n\n'+status+'\n[历史评审索引](REVIEW_INDEX.md)\n',encoding='utf-8')
 p=REPO/'REVIEW_INDEX.md';prior=p.read_text(encoding='utf-8') if p.exists() else ''
 p.write_text('# 最新完整评审入口\n\n['+SLUG+']('+REL+'/FINAL_REVIEW.md) · [完整ZIP]('+release_url+') · [展开目录]('+REL+')。\n\n---\n\n'+prior,encoding='utf-8')
 git('add','--',REL,'README.md','PROJECT_STATUS.md','REVIEW_INDEX.md')
 git('commit','-m','Complete common-C0 fixed-schedule D crossover and full evidence review')
 head=git('rev-parse','HEAD');assert not git('status','--porcelain')
 dump('GITHUB_R3_PUBLICATION_PREPARED.json',{'commit':head,'parent':parent,'branch':BRANCH,'package':package,'published':False})
 git('push','-u','origin',BRANCH,timeout=600)
 assert git('ls-remote','--heads','origin','refs/heads/'+BRANCH).split()[0]==head
 expected={}
 for row in git('-c','core.quotepath=false','ls-tree','-r',head).splitlines():
  meta,p=row.split('\t',1);mode,kind,h=meta.split()
  if kind=='blob':expected[p]=h
 tree=api('/repos/Pseven0108/GameCam-VO/git/trees/'+head+'?recursive=1',token);assert not tree.get('truncated')
 assert {x['path']:x['sha'] for x in tree['tree'] if x['type']=='blob'}==expected
 try:release=api('/repos/Pseven0108/GameCam-VO/releases/tags/'+TAG,token)
 except urllib.error.HTTPError as e:
  if e.code!=404:raise
  release=api('/repos/Pseven0108/GameCam-VO/releases',token,method='POST',body={'tag_name':TAG,'target_commitish':head,'name':'Task004C-B full crossover review','body':'CRC/SHA-verified complete review and expanded evidence at commit '+head+'. One sequence, one seed; large native dataset/model payloads inventoried and retained locally.','draft':False,'prerelease':False})
 assets=api('/repos/Pseven0108/GameCam-VO/releases/'+str(release['id'])+'/assets',token)
 assert not any(a['name']==package['ZIP'] for a in assets),'Existing asset: reconcile, do not replace'
 upload=release['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(package['ZIP'])
 req=urllib.request.Request(upload,data=zp.read_bytes(),method='POST',headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/zip','User-Agent':'GameCam-VO-review-publication'})
 with urllib.request.urlopen(req,timeout=600) as r:asset=json.load(r)
 assert asset['state']=='uploaded' and asset['size']==package['ZIP_bytes']
 anon=EXTERNAL_ROOT/'ANONYMOUS_RELEASE_VERIFICATION.zip';assert not anon.exists()
 req=urllib.request.Request(asset['browser_download_url'],headers={'User-Agent':'GameCam-VO-anonymous-verification'})
 with urllib.request.urlopen(req,timeout=180) as r,anon.open('xb') as f:shutil.copyfileobj(r,f,8*1024**2)
 assert sha(anon)==package['ZIP_sha256']
 with zipfile.ZipFile(anon) as z:
  assert z.testzip() is None;m=json.loads(z.read('FILE_SHA256_MANIFEST.json'))
  assert set(z.namelist())==set(m['files'])|{'FILE_SHA256_MANIFEST.json'}
  for n,want in m['files'].items():
   h=hashlib.sha256();size=0
   with z.open(n) as f:
    for b in iter(lambda:f.read(8*1024**2),b''):h.update(b);size+=len(b)
   assert h.hexdigest()==want['sha256'] and size==want['bytes'],n
 for p in (REL+'/FINAL_REVIEW.md',REL+'/FILE_SHA256_MANIFEST.json',REL+'/evaluation/CROSSOVER_SUMMARY.csv','PROJECT_STATUS.md'):
  req=urllib.request.Request('https://raw.githubusercontent.com/Pseven0108/GameCam-VO/'+head+'/'+p,headers={'User-Agent':'GameCam-VO-anonymous-verification'})
  with urllib.request.urlopen(req,timeout=90) as r:b=r.read()
  assert b==(REPO/p).read_bytes(),p
 after=api('/repos/Pseven0108/GameCam-VO',token);assert after['private']==before['private'] and after['default_branch']==before['default_branch']
 receipt={'published':True,'commit':head,'branch':BRANCH,'release_tag':TAG,'review_URL':'https://github.com/Pseven0108/GameCam-VO/blob/'+head+'/'+REL+'/FINAL_REVIEW.md','raw_review_URL':'https://raw.githubusercontent.com/Pseven0108/GameCam-VO/'+head+'/'+REL+'/FINAL_REVIEW.md','directory_URL':'https://github.com/Pseven0108/GameCam-VO/tree/'+head+'/'+REL,'ZIP_URL':asset['browser_download_url'],'ZIP_SHA256':package['ZIP_sha256'],'ZIP_bytes':package['ZIP_bytes'],'anonymous_download_and_SHA':'PASS','anonymous_CRC':'PASS','internal_manifest_all_match':True,'remote_blob_count_verified':len(expected),'repository_visibility_changed':False,'default_branch_changed':False,'prior_staged_draft_untouched':True}
 dump('GITHUB_R3_PUBLICATION_RECEIPT.json',receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
