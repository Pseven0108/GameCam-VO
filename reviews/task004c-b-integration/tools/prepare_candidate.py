import hashlib, json, pathlib, shutil, subprocess
from datetime import datetime, timezone
ROOT=pathlib.Path(__file__).resolve().parents[1]
before=ROOT/'source_before';candidate=ROOT/'source_candidate'
assert not list(candidate.iterdir()), 'Independent candidate must be new'
records=[]
for p in sorted(before.rglob('*')):
    if p.is_file():
        rel=p.relative_to(before); dest=candidate/rel
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        a=hashlib.sha256(p.read_bytes()).hexdigest();b=hashlib.sha256(dest.read_bytes()).hexdigest()
        assert a==b
        records.append({'path':rel.as_posix(),'sha256':a,'initial_copy_match':True})
def git(*args):
    q=subprocess.run(['git','-C',str(candidate),*args],capture_output=True,text=True,check=True)
    return q.stdout.strip()
git('init','--initial-branch=codex/task004c-b-native-integration')
git('-c','user.name=GameCam Native Integration','-c','user.email=gamecam@localhost','add','--all')
git('-c','user.name=GameCam Native Integration','-c','user.email=gamecam@localhost','commit','-m','Freeze audited execution text tree before native integration')
meta={'schema':'NATIVE_BASELINE_MANIFEST_V1','upstream_commit':'c3414af6047d06bafc1a6645d09f23247f3b2cdc',
      'kind':'LOCAL_TEXT_REFERENCE_SUBSET_OF_REMOTE_FULL_TREE','local_baseline_commit':git('rev-parse','HEAD'),
      'copied_files':records,'remote_full_tree_manifest':'PHASE0.json:source_manifest',
      'original_remote_is_git_checkout':False,'candidate_created_utc':datetime.now(timezone.utc).isoformat()}
(ROOT/'evidence/LOCAL_BASELINE_MANIFEST.json').write_text(json.dumps(meta,indent=2))
# The process command lines from Phase0 are private. Publish a sanitized view only.
p=json.loads((ROOT/'evidence/PHASE0.json').read_text()); ps=p.pop('processes',None)
p['processes_redacted']={'reason':'Full process command lines can contain access tokens; omitted from review bundle', 'read_only_process_inspection_performed':ps is not None}
(ROOT/'evidence/PHASE0_REVIEW_SAFE.json').write_text(json.dumps(p,indent=2))
print(json.dumps({'local_text_files_copied':len(records),'baseline_git_commit':meta['local_baseline_commit'],
                 'remote_files':len(p['source_manifest']),'remote_file_bytes':sum(x.get('bytes',0) for x in p['source_manifest'])}))
