"""Read current GitHub identities; never print or persist credentials."""
import pathlib,sys,json,os
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,r'D:\aaa\GameCam-VO\maintenance\GITHUB_REVIEW_PUBLICATION_20261124_R1')
from github_readonly import credential,api

if __name__=='__main__':
    token=credential();repo=api('/repos/Pseven0108/GameCam-VO',token)
    refs=api('/repos/Pseven0108/GameCam-VO/git/matching-refs/heads/codex/',token)
    selected={x['ref']:x['object']['sha'] for x in refs if any(v in x['ref'] for v in ('task005','task004c-b-crossover'))}
    data={'repository':repo['full_name'],'private':repo['private'],'default_branch':repo['default_branch'],
          'protected_prior_refs':selected,'new_branch':'codex/task005b-gpu-mechanism-20261125',
          'new_release_tag':'task005b-gpu-mechanism-20261125','visibility_change_authorized_or_performed':False}
    target=ROOT/'07_release/GITHUB_INTAKE.json'
    with target.open('x') as f:json.dump(data,f,indent=2)
    print(json.dumps(data))
