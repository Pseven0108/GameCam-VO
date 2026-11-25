import os,sys,pathlib,json
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,r'D:\aaa\GameCam-VO\maintenance\GITHUB_REVIEW_PUBLICATION_20261124_R1')
from github_readonly import credential,api
token=credential();base='/repos/Pseven0108/GameCam-VO'
repo=api(base,token);refs=api(base+'/git/matching-refs/heads/',token)
prior=api(base+'/git/ref/heads/codex/task005b-gpu-mechanism-20261125',token)
assert prior['object']['sha']=='961cf638a759cf6275351bfad0c335bc8f40cd00'
assert not repo['private']
proof={'repository':repo['full_name'],'private':repo['private'],'default_branch':repo['default_branch'],'parent_commit':prior['object']['sha'],'protected_prior_heads':{r['ref']:r['object']['sha'] for r in refs},'new_branch':'codex/task005b-r2-native-numerics-20261125','new_release':'task005b-r2-native-numerics-20261125','existing_credentials_reused':True,'token_printed':False}
with (ROOT/'07_release/GITHUB_INTAKE.json').open('x',encoding='utf-8') as f:json.dump(proof,f,indent=2)
print(json.dumps({k:v for k,v in proof.items() if k!='protected_prior_heads'},indent=2))
