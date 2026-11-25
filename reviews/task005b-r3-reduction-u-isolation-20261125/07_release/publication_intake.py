import os,sys,pathlib,json,time
os.environ['CUDA_VISIBLE_DEVICES']=''
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,r'D:\aaa\GameCam-VO\maintenance\GITHUB_REVIEW_PUBLICATION_20261124_R1')
from github_readonly import credential,api
token=credential();base='/repos/Pseven0108/GameCam-VO'
repo=api(base,token);refs={r['ref']:r['object']['sha'] for r in api(base+'/git/matching-refs/heads/',token)}
slug='task005b-r3-reduction-u-isolation-20261125';assert 'refs/heads/codex/'+slug not in refs
parent=refs['refs/heads/codex/task005b-r2-native-numerics-20261125']
assert parent=='ae3ad293a337f0fec91e604c1fa34fa72aed25b3'
result={'repository':repo['full_name'],'private':repo['private'],'default_branch':repo['default_branch'],'parent_commit':parent,'protected_prior_heads':refs,'new_branch':'codex/'+slug,'new_release':slug,'existing_credentials_reused':True,'token_printed':False,'started_unix':time.time()}
with (ROOT/'07_release/GITHUB_INTAKE.json').open('x',encoding='utf-8') as f:f.write(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='protected_prior_heads'},indent=2))
