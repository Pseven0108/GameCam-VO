"""Publish TASK005A on a new branch, preserving immutable Task004C-B refs."""
import os,sys,pathlib,json,subprocess,shutil,urllib.request,urllib.error,urllib.parse,zipfile,hashlib
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
from task005a_analysis import ROOT,RECEIVER,sha,dump,verify_seal
sys.path.insert(0,r'D:\aaa\GameCam-VO\maintenance\GITHUB_REVIEW_PUBLICATION_20261124_R1')
from github_readonly import credential,api
SLUG='task005a-d-schedule-mechanism-20261125';BRANCH='codex/'+SLUG;REL='reviews/'+SLUG
REPO=RECEIVER/'publication_repository_task005a';SOURCE=RECEIVER/'publication_repository_r3';PARENT='d9656b66eb541b6f3889e41cd8329898edc6f0c8'
ENV=dict(os.environ,GCM_INTERACTIVE='Never',GIT_TERMINAL_PROMPT='0',CUDA_VISIBLE_DEVICES='')
def cmd(args,timeout=180):
 p=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',env=ENV,timeout=timeout)
 if p.returncode:raise RuntimeError({'command':args[0],'exit_code':p.returncode,'stderr':p.stderr[-1400:]})
 return p.stdout.strip()
def git(*args,timeout=180):return cmd(['git','-C',str(REPO),*args],timeout)
def main():
 package=json.loads((ROOT/'08_release/PACKAGE_VALIDATION.json').read_text());assert package['status']=='PASS' and package['manifest_all_match'];verify_seal()
 token=credential();before=api('/repos/Pseven0108/GameCam-VO',token)
 oldref=api('/repos/Pseven0108/GameCam-VO/git/ref/heads/codex/task004c-b-crossover-full-20261125',token)['object']['sha'];assert oldref==PARENT
 try:
  prior=api('/repos/Pseven0108/GameCam-VO/git/ref/heads/'+BRANCH,token);raise RuntimeError('Target TASK005A branch already exists; reconcile receipt instead of replacing it.')
 except urllib.error.HTTPError as err:
  if err.code!=404:raise
 assert not REPO.exists(),'Do not overwrite a publication checkout; inspect current prepared receipt.'
 cmd(['git','clone','--no-hardlinks','--no-checkout',str(SOURCE),str(REPO)],timeout=300)
 git('remote','set-url','origin','https://github.com/Pseven0108/GameCam-VO.git');git('checkout','-b',BRANCH,PARENT)
 for key in ('user.name','user.email'):
  value=cmd(['git','-C',str(SOURCE),'config','--get',key]);git('config',key,value)
 assert not git('status','--porcelain')
 old_tree=git('rev-parse',PARENT+':reviews/task004c-b-crossover-full-20261125')
 shutil.copytree(package['expanded_review'],REPO/REL)
 zurl='https://github.com/Pseven0108/GameCam-VO/releases/download/'+SLUG+'/'+package['ZIP']
 status='''# GameCam-VO · TASK005A\n\nTask004C-B 已封存为本项目第一项完整四组受控交叉实验；其固定提交和完整ZIP保持不变。TASK005A只分析已有证据，新增GPU运行0次，22项CPU检查通过。\n\nD×S反转在相同72个真实关键帧的前端位置Sim(3)ATE已存在；D同时改变深度对角正则与先验梯度，随后Pose/disparity/U/对应关系连续反馈。尺度诊断和姿态误差并不具有相同反转，不能声称D普遍有害或已唯一锁定Metric3D错误。\n\n[最终报告]('''+REL+'''/FINAL_REVIEW.md) · [完整ZIP]('''+zurl+''') · [展开证据]('''+REL+''') · [原实验封存决定]('''+REL+'''/TASK004CB_FORMAL_SEAL.md)。\n\n本轮未连接或启停实例，未修改旧结果，未开展下一阶段GPU实验。\n'''
 (REPO/'PROJECT_STATUS.md').write_text(status,encoding='utf-8');(REPO/'README.md').write_text(status+'\n[历史评审索引](REVIEW_INDEX.md)\n',encoding='utf-8')
 idx=REPO/'REVIEW_INDEX.md';prior=idx.read_text(encoding='utf-8') if idx.exists() else ''
 idx.write_text('# 最新评审\n\n['+SLUG+']('+REL+'/FINAL_REVIEW.md) · [完整ZIP]('+zurl+') · [展开文件]('+REL+')。\n\n---\n\n'+prior,encoding='utf-8')
 git('add','--',REL,'README.md','PROJECT_STATUS.md','REVIEW_INDEX.md');git('commit','-m','Seal first complete crossover and analyze schedule-conditional depth regularization')
 head=git('rev-parse','HEAD');assert not git('status','--porcelain');assert git('rev-parse','HEAD:reviews/task004c-b-crossover-full-20261125')==old_tree
 dump(ROOT/'08_release/GITHUB_PREPARED.json',{'artifact_commit':head,'parent':PARENT,'branch':BRANCH,'package':package,'published':False})
 git('push','-u','origin',BRANCH,timeout=600);assert git('ls-remote','--heads','origin','refs/heads/'+BRANCH).split()[0]==head
 expected={}
 for line in git('-c','core.quotepath=false','ls-tree','-r',head).splitlines():
  m,p=line.split('\t',1);mode,kind,digest=m.split()
  if kind=='blob':expected[p]=digest
 remote=api('/repos/Pseven0108/GameCam-VO/git/trees/'+head+'?recursive=1',token);assert not remote.get('truncated');assert {x['path']:x['sha'] for x in remote['tree'] if x['type']=='blob'}==expected
 try:release=api('/repos/Pseven0108/GameCam-VO/releases/tags/'+SLUG,token)
 except urllib.error.HTTPError as err:
  if err.code!=404:raise
  release=api('/repos/Pseven0108/GameCam-VO/releases',token,method='POST',body={'tag_name':SLUG,'target_commitish':head,'name':'TASK005A D × schedule offline mechanism review','body':'Complete new review package and expanded evidence at '+head+'. Task004C-B remains immutable. Zero new GPU runs; 22 CPU checks; primary attribution remains unresolved.','draft':False,'prerelease':False})
 assets=api('/repos/Pseven0108/GameCam-VO/releases/'+str(release['id'])+'/assets',token);assert not any(x['name']==package['ZIP'] for x in assets),'Existing release asset: reconcile, never replace.'
 upload=release['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(package['ZIP']);zp=pathlib.Path(package['ZIP_path'])
 request=urllib.request.Request(upload,data=zp.read_bytes(),method='POST',headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/zip','User-Agent':'GameCam-VO-review-publication'})
 with urllib.request.urlopen(request,timeout=300) as response:asset=json.load(response)
 assert asset['state']=='uploaded' and asset['size']==package['ZIP_bytes']
 anon_status='NOT_PUBLIC_NOT_ATTEMPTED'
 if not before['private']:
  anon=RECEIVER/'TASK005A_ANONYMOUS_RELEASE_VERIFICATION.zip';assert not anon.exists()
  request=urllib.request.Request(asset['browser_download_url'],headers={'User-Agent':'GameCam-VO-anonymous-verification'})
  with urllib.request.urlopen(request,timeout=120) as response,anon.open('xb') as output:shutil.copyfileobj(response,output,1024**2)
  assert sha(anon)==package['ZIP_sha256']
  with zipfile.ZipFile(anon) as z:
   assert z.testzip() is None;manifest=json.loads(z.read('FILE_SHA256_MANIFEST.json'));assert set(z.namelist())==set(manifest['files'])|{'FILE_SHA256_MANIFEST.json'}
   for name,want in manifest['files'].items():
    data=z.read(name);assert len(data)==want['bytes'] and hashlib.sha256(data).hexdigest()==want['sha256']
  for name in ['FINAL_REVIEW.md','FILE_SHA256_MANIFEST.json','03_evaluation/TASK005A_CONDITIONAL_D_EFFECTS.csv']:
   request=urllib.request.Request('https://raw.githubusercontent.com/Pseven0108/GameCam-VO/'+head+'/'+REL+'/'+name,headers={'User-Agent':'GameCam-VO-anonymous-verification'})
   with urllib.request.urlopen(request,timeout=90) as response:data=response.read()
   assert data==(REPO/REL/name).read_bytes()
  anon_status='PASS_DOWNLOAD_SHA_CRC_MANIFEST_AND_RAW_FILES'
 after=api('/repos/Pseven0108/GameCam-VO',token);assert after['private']==before['private'] and after['default_branch']==before['default_branch']
 assert api('/repos/Pseven0108/GameCam-VO/git/ref/heads/codex/task004c-b-crossover-full-20261125',token)['object']['sha']==oldref
 receipt={'published':True,'artifact_commit':head,'branch':BRANCH,'release_tag':SLUG,'review_URL':'https://github.com/Pseven0108/GameCam-VO/blob/'+head+'/'+REL+'/FINAL_REVIEW.md','raw_review_URL':'https://raw.githubusercontent.com/Pseven0108/GameCam-VO/'+head+'/'+REL+'/FINAL_REVIEW.md','directory_URL':'https://github.com/Pseven0108/GameCam-VO/tree/'+head+'/'+REL,'ZIP_URL':asset['browser_download_url'],'ZIP_SHA256':package['ZIP_sha256'],'ZIP_bytes':package['ZIP_bytes'],'ZIP_members':package['ZIP_members'],'manifest_items':package['manifest_items'],'anonymous_verification':anon_status,'repository_private':after['private'],'repository_visibility_changed':False,'default_branch_changed':False,'old_Task004CB_ref_unchanged':True,'old_Task004CB_review_tree_unchanged':True,'remote_blobs_verified':len(expected),'new_GPU_runs':0}
 ops=REPO/'operations'/SLUG;ops.mkdir(parents=True);(ops/'PUBLICATION_VERIFICATION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 git('add','--','operations/'+SLUG+'/PUBLICATION_VERIFICATION.json');git('commit','-m','Record TASK005A archive verification and preserved prior experiment identity');final=git('rev-parse','HEAD');git('push','origin',BRANCH,timeout=300)
 assert git('ls-remote','--heads','origin','refs/heads/'+BRANCH).split()[0]==final;receipt['receipt_commit']=final
 dump(ROOT/'08_release/GITHUB_PUBLICATION_RECEIPT.json',receipt);verify_seal();print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
