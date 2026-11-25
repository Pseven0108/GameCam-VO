"""Publish a new isolated review branch and a full immutable evidence Release."""
import os,sys,pathlib,json,subprocess,shutil,urllib.request,urllib.error,urllib.parse,hashlib,zipfile,argparse,time
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'07_release'))
from package_review import sha,prove_zip
sys.path.insert(0,r'D:\aaa\GameCam-VO\maintenance\GITHUB_REVIEW_PUBLICATION_20261124_R1')
from github_readonly import credential,api
RECV=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-R3-20261125-R1')
SOURCE=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-R2-20261125-R1\publication_repository_task005b_r2_numerics')
REPO=RECV/'publication_repository_task005b_r3_reduction_U'
BASE='/repos/Pseven0108/GameCam-VO';SLUG='task005b-r3-reduction-u-isolation-20261125';BRANCH='codex/'+SLUG;REL='reviews/'+SLUG
ENV=dict(os.environ,GCM_INTERACTIVE='Never',GIT_TERMINAL_PROMPT='0',CUDA_VISIBLE_DEVICES='')
def read(name):return json.loads((ROOT/'07_release'/name).read_text(encoding='utf-8'))
def save(name,value):(ROOT/'07_release'/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def cmd(args,timeout=180):
 p=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',env=ENV,timeout=timeout)
 if p.returncode:raise RuntimeError({'program':args[0],'exit':p.returncode,'stderr':p.stderr[-1500:]})
 return p.stdout.strip()
def git(*args,timeout=180):return cmd(['git','-C',str(REPO),*args],timeout)
def protect(token):
 intake=read('GITHUB_INTAKE.json');refs={r['ref']:r['object']['sha'] for r in api(BASE+'/git/matching-refs/heads/',token)}
 assert all(refs.get(k)==v for k,v in intake['protected_prior_heads'].items())
 repo=api(BASE,token);assert (repo['private'],repo['default_branch'])==(intake['private'],intake['default_branch'])
 return {'protected_prior_heads':len(intake['protected_prior_heads']),'all_preserved':True,'default_branch_unchanged':True,'visibility_unchanged':True}
def prepare():
 intake=read('GITHUB_INTAKE.json');p=read('PACKAGE_VALIDATION.json');assert p['PASS']
 token=credential();proof=protect(token)
 refs={r['ref']:r['object']['sha'] for r in api(BASE+'/git/matching-refs/heads/',token)}
 assert 'refs/heads/'+BRANCH not in refs
 assert not REPO.exists()
 cmd(['git','clone','--no-hardlinks','--no-checkout',str(SOURCE),str(REPO)],300)
 git('config','core.longpaths','true');git('remote','set-url','origin','https://github.com/Pseven0108/GameCam-VO.git')
 for key in ('user.name','user.email'):git('config',key,cmd(['git','-C',str(SOURCE),'config','--get',key]))
 git('checkout','-b',BRANCH,intake['parent_commit']);assert not git('status','--porcelain')
 shutil.copytree(p['browse_directory'],REPO/REL)
 url='https://github.com/Pseven0108/GameCam-VO/releases/download/'+SLUG+'/'+p['ZIP']
 status=f'''# GameCam-VO · TASK005B-R3 reduction and U feedback isolation

Completed 16 isolated Jjj calls, 16 isolated J_linear calls and 20 two-iteration BA replays on the sealed D0_S1_RGB233 context. Both isolated reductions fluctuate under fixed inputs. Fixed U retains native affine/temp updates and blocks only U feedback into the next round. See the final report for endpoint gates, causal limits and readiness decisions. No S0, remaining S1 matrix, full-sequence model run or shutdown.

[Final review]({REL}/FINAL_REVIEW.md) · [Isolation results]({REL}/R3_REDUCTION_ISOLATION.md) · [U feedback]({REL}/R3_U_FEEDBACK.md) · [Readiness decision]({REL}/R3_CANDIDATE_READINESS.md) · [Complete review ZIP]({url})

The complete ZIP ({p['ZIP_bytes']:,} bytes) contains the exact full input archive, fixed R2 intermediate, all 52 output NPZ files, complete scientific logs and independent diagnostic binary. CRC and all {p['manifest_items']} internal SHA-256 entries verified. Reports and CSV files are expanded for direct review.

Task004C-B, Task005A, TASK005B-R1 and R2 remain sealed. Instance remains running.
'''
 for n in ('README.md','PROJECT_STATUS.md'):(REPO/n).write_text(status,encoding='utf-8')
 index=REPO/'REVIEW_INDEX.md';prior=index.read_text(encoding='utf-8') if index.exists() else ''
 index.write_text(f'# TASK005B-R3 latest review\n\n[Expanded review]({REL}/FINAL_REVIEW.md) · [Entire evidence ZIP]({url})\n\n---\n\n'+prior,encoding='utf-8')
 git('add','--','README.md','PROJECT_STATUS.md','REVIEW_INDEX.md');git('add','-f','--',REL)
 git('commit','-m','Record TASK005B-R3 isolated reductions and U feedback controls')
 head=git('rev-parse','HEAD')
 for name in ['task004c-b-crossover-full-20261125','task005a-d-schedule-mechanism-20261125','task005b-depth-path-preparation-20261125','task005b-gpu-mechanism-20261125','task005b-r2-native-numerics-20261125']:
  assert git('rev-parse',intake['parent_commit']+':reviews/'+name)==git('rev-parse',head+':reviews/'+name)
 result={'artifact_commit':head,'branch':BRANCH,'repository':str(REPO),'review_path':REL,'prepared':True,'published':False,'historical_protection':proof,'package_SHA':p['ZIP_sha256']}
 save('GITHUB_PREPARED.json',result);print(json.dumps(result,indent=2))
def publish():
 prep=read('GITHUB_PREPARED.json');p=read('PACKAGE_VALIDATION.json');token=credential();protect(token)
 assert git('rev-parse','HEAD')==prep['artifact_commit'] and not git('status','--porcelain')
 assert sha(p['ZIP_path'])==p['ZIP_sha256']
 if not git('ls-remote','--heads','origin','refs/heads/'+BRANCH):git('push','-u','origin',BRANCH,timeout=600)
 assert git('ls-remote','--heads','origin','refs/heads/'+BRANCH).split()[0]==prep['artifact_commit']
 tree=api(BASE+'/git/trees/'+prep['artifact_commit']+'?recursive=1',token);assert not tree.get('truncated')
 blobs={v['path']:v['sha'] for v in tree['tree'] if v['type']=='blob'};count=0
 for path in (REPO/REL).rglob('*'):
  if path.is_file():
   raw=path.read_bytes();expect=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
   assert blobs[path.relative_to(REPO).as_posix()]==expect;count+=1
 try:release=api(BASE+'/releases/tags/'+SLUG,token)
 except urllib.error.HTTPError as e:
  if e.code!=404:raise
  release=api(BASE+'/releases',token,method='POST',body={'tag_name':SLUG,'target_commitish':prep['artifact_commit'],'name':'TASK005B-R3 — isolated CUDA reductions and U feedback review','body':'Completed 16 isolated Jjj calls, 16 isolated J_linear calls and 20 two-iteration native BA controls. Both atomic reductions fluctuate independently. U-only fixed controls retain native affine/temp updates. Complete evidence, unchanged-tolerance checks and readiness limits are in the final report and ZIP. No S0 or remaining mechanism-matrix expansion.','draft':False,'prerelease':True})
 assert release['target_commitish']==prep['artifact_commit']
 assets=api(BASE+'/releases/'+str(release['id'])+'/assets',token)
 matches=[a for a in assets if a['name']==p['ZIP']];assert len(matches)<=1
 if matches:asset=matches[0]
 else:
  save('GITHUB_UPLOAD_STARTED.json',{'release_id':release['id'],'asset':p['ZIP'],'bytes':p['ZIP_bytes'],'sha256':p['ZIP_sha256'],'started_unix':time.time(),'automatic_retry':False})
  url=release['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(p['ZIP'])
  headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/zip','Content-Length':str(p['ZIP_bytes']),'User-Agent':'GameCam-VO-review-publication'}
  with pathlib.Path(p['ZIP_path']).open('rb') as stream:
   req=urllib.request.Request(url,data=stream,method='POST',headers=headers)
   with urllib.request.urlopen(req,timeout=900) as response:asset=json.load(response)
 assert asset['state']=='uploaded' and asset['size']==p['ZIP_bytes'] and asset.get('digest')=='sha256:'+p['ZIP_sha256']
 receipt={'published':True,'artifact_commit':prep['artifact_commit'],'branch':BRANCH,'review_URL':'https://github.com/Pseven0108/GameCam-VO/blob/'+prep['artifact_commit']+'/'+REL+'/FINAL_REVIEW.md','review_directory_URL':'https://github.com/Pseven0108/GameCam-VO/tree/'+prep['artifact_commit']+'/'+REL,'release_URL':release['html_url'],'release_id':release['id'],'ZIP_URL':asset['browser_download_url'],'ZIP_bytes':asset['size'],'ZIP_sha256':p['ZIP_sha256'],'GitHub_asset_digest':asset['digest'],'expanded_review_blobs_verified':count,'historical_protection':protect(token),'default_branch_or_visibility_modified':False}
 save('GITHUB_PUBLICATION_RECEIPT.json',receipt);print(json.dumps(receipt,indent=2))
def verify():
 receipt=read('GITHUB_PUBLICATION_RECEIPT.json');p=read('PACKAGE_VALIDATION.json');token=credential()
 ua={'User-Agent':'GameCam-VO-anonymous-review-verification'}
 download=RECV/'ANONYMOUS_REVIEW_DOWNLOAD.zip';assert not download.exists()
 with urllib.request.urlopen(urllib.request.Request(receipt['ZIP_URL'],headers=ua),timeout=300) as response,download.open('xb') as f:shutil.copyfileobj(response,f)
 assert download.stat().st_size==p['ZIP_bytes'] and sha(download)==p['ZIP_sha256']
 count=prove_zip(download);checks=[]
 for name in ['FINAL_REVIEW.md','R3_DECISION.json','R3_U_FEEDBACK.md','04_analysis/ISOLATED_SUMMARY.json','04_analysis/BA_REPEATABILITY_SUMMARY.csv']:
  url='https://raw.githubusercontent.com/Pseven0108/GameCam-VO/'+receipt['artifact_commit']+'/'+REL+'/'+name
  with urllib.request.urlopen(urllib.request.Request(url,headers=ua),timeout=60) as response:b=response.read()
  assert b==(REPO/REL/name).read_bytes();checks.append(name)
 receipt['anonymous_verification']={'ZIP_downloaded_bytes':download.stat().st_size,'ZIP_SHA_matches':True,'ZIP_CRC_PASS':True,'all_manifest_SHA_verified':count,'fixed_commit_raw_files_match':checks,'authentication_used_for_download':False}
 save('GITHUB_PUBLICATION_RECEIPT.json',receipt)
 ops=REPO/'operations'/SLUG;ops.mkdir(parents=True,exist_ok=False)
 (ops/'PUBLICATION_VERIFICATION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 git('add','--','operations/'+SLUG+'/PUBLICATION_VERIFICATION.json');git('commit','-m','Verify anonymous full TASK005B-R3 review archive and fixed-commit reports')
 receipt['receipt_commit']=git('rev-parse','HEAD');git('push','origin',BRANCH,timeout=300);receipt['historical_protection']=protect(token)
 save('GITHUB_PUBLICATION_RECEIPT.json',receipt);print(json.dumps(receipt,indent=2))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','publish','verify']);args=parser.parse_args()
 {'prepare':prepare,'publish':publish,'verify':verify}[args.action]()
