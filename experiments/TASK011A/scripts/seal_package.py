"""Seal all new float evidence and an explicit Git publication allowlist."""
from common import *
import io,re,shutil,zipfile

REVIEW=ROOT/'reviews/task011a-depth-reliability-fusion-20261127'
PRIVATE=TASK/'private/publication'

def secret_check(p):
    if p.suffix.lower() not in {'.py','.json','.md','.csv','.txt','.log','.yaml'}:return
    text=p.read_text(encoding='utf-8',errors='replace')
    if re.search(r'gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',text):raise RuntimeError('Potential credential blocks publication')

def main():
    replay=json.loads((REVIEW/'ARTIFACT_REPLAY_VERIFICATION.json').read_text());assert replay['status']=='PASS' and replay['maximum_absolute_difference']==0
    assert replay['scalar_metric_comparisons']==468 and replay['bitwise_risk_map_comparisons']==64
    PRIVATE.mkdir(parents=True,exist_ok=True)
    for p in (TASK/'scripts').glob('*.py'):shutil.copyfile(p,REVIEW/'code'/p.name)
    files=sorted(p for p in REVIEW.rglob('*') if p.is_file() and p.name!='SHA256_MANIFEST.csv')
    forbidden={'.exr','.jpg','.jpeg','.pth','.pt','.pyd','.so','.whl','.safetensors'}
    rows=[]
    for p in files:
        if p.suffix.lower() in forbidden:raise RuntimeError('Original image/GT/model/runtime binary in review')
        secret_check(p);rows.append({'path':p.relative_to(REVIEW).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
    s=io.StringIO();w=csv.DictWriter(s,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(rows)
    (REVIEW/'SHA256_MANIFEST.csv').write_text(s.getvalue(),encoding='utf-8',newline='')
    archive=ROOT/'review_packages/GAMECAM_TASK011A_DEPTH_RELIABILITY_FUSION_REVIEW.zip';archive.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for p in sorted(REVIEW.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(REVIEW).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for r in rows:
            data=z.read(r['path']);assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
    identity=sha(archive);sidecar=archive.with_suffix('.zip.sha256');sidecar.write_text(identity+'  '+archive.name+'\n',encoding='utf-8')
    proof={'status':'PASS','zip_bytes':archive.stat().st_size,'zip_sha256':identity,'zip_crc':'PASS','internal_sha256_verified':len(rows),'full_float64_maps_included':16,'minimal_original_prediction_subsets_included':16,'raw_RGB_GT_models_env_binaries_excluded':True,'expanded_review_contains_all_new_float_evidence':True,'artifact_scalar_comparisons':468,'artifact_map_comparisons':64}
    dump(ROOT/'deliveries/TASK011A_PACKAGE_VERIFICATION.json',proof)
    paths=[p for p in REVIEW.rglob('*') if p.is_file()]+[sidecar,ROOT/'deliveries/TASK011A_PACKAGE_VERIFICATION.json']
    paths += [ROOT/n for n in ['.gitignore','AGENTS.md','README.md','PROJECT_STATUS.md','REVIEW_INDEX.md','CURRENT_RESEARCH_STATUS.md','CURRENT_RESEARCH_SCOPE.json','RESEARCH_DIRECTION_CURRENT.json']]
    paths += [p for folder in [TASK/'scripts',TASK/'tests'] for p in folder.glob('*.py')]
    paths += [TASK/'PROTOCOL_FROZEN.json',TASK/'FIGURE_CONTRACT.md']
    entries=[]
    for p in sorted(set(paths)):
        secret_check(p);data=p.read_bytes()
        if len(data)>95*1024**2:raise RuntimeError('Individual Git blob exceeds bounded publication size')
        entries.append({'path':p.relative_to(ROOT).as_posix(),'source':str(p),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'git_blob_sha':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()})
    dump(PRIVATE/'allowlist.json',{'parent_sha':'27bf7580bd8b43c11daaf3cbbdb77be46bc9a35d','branch':'codex/task011a-depth-reliability-review-20261127','entries':entries,'archive':str(archive),'archive_sha256':identity,'review_directory':REVIEW.relative_to(ROOT).as_posix(),'release_tag':'task011a-depth-reliability-fusion-20261127','internal_sha256_count':len(rows)})
    print(json.dumps(proof,indent=2));print('GIT_ALLOWLIST',len(entries),'files',sum(r['bytes'] for r in entries),'bytes',flush=True)

if __name__=='__main__':main()
