from transport import *
import io,tarfile,ast,difflib
for name in ('task004_controls.py','task004_run_segment.py'):
 old=(A/'release/candidates'/name).read_text();new=(ROOT/'release/candidates'/name).read_text();ast.parse(new)
 (ROOT/'release'/('B_vs_A_'+name+'.diff')).write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='Task004A/'+name,tofile='Task004B/'+name)),encoding='utf-8')
pins={p.relative_to(ROOT/'release').as_posix():sha(p) for p in (ROOT/'release').rglob('*') if p.is_file()}
prior=ROOT/'release/RELEASE_SHA256.json'
if prior.exists():
 pins.pop('RELEASE_SHA256.json',None);assert json.loads(prior.read_text())==pins
else:put(prior,pins)
buf=io.BytesIO()
with tarfile.open(fileobj=buf,mode='w:gz') as t:
 for p in (ROOT/'release').rglob('*'):
  if p.is_file():t.add(p,arcname=p.relative_to(ROOT/'release').as_posix())
storage=json.loads((ROOT/'evidence/STORAGE_PREFLIGHT_V2.json').read_text());assert storage['local_ready'] and storage['remote_ready']
spec=dict(root=REMOTE,a='/root/rivermind-data/'+A.name,hostname='jupyter-yd6gks8uzfbxzdb4',budget=storage['remote_required'],storage_plan=storage,release=base64.b64encode(buf.getvalue()).decode(),viewer_bin=json.loads((A/'bootstrap/evidence/BOOTSTRAP_PASS.json').read_text())['viewer']['native_identity']['executable'])
out=rpc((ROOT/'tools/remote_prepare.py').read_text(),spec,'PREPARE_AUTHORIZED_SEED_RELEASE_V2',timeout=300)
put(ROOT/'evidence/REMOTE_PREPARE_RECEIPT.json',out);print(json.dumps(out))
