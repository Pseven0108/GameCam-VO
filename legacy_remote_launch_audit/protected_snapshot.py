"""Read-only byte-integrity checks against approved manifests and before/after snapshots."""
import datetime, hashlib, json, pathlib, sys
BASE=pathlib.Path('/root/rivermind-data/gamecam'); ROOT=BASE/'GameCam-VO'; SETUP=BASE/'setup'
BUILD=pathlib.Path('/opt/gamecam/build-src/droid-w')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
    return h.hexdigest()
def capture():
    latest_path=SETUP/'R2_RECOVERY_latest_validated.json'
    latest=json.loads(latest_path.read_text()); validated=pathlib.Path(latest['validated_evidence_dir']); build=pathlib.Path(latest['build_evidence_dir'])
    if latest['status']!='CPU_PREPARATION_VALIDATED_WAITING_FOR_GPU' or not all(latest['checks'].values()): raise RuntimeError('Latest CPU pointer is not accepted')
    local=pathlib.Path(__file__).parent; paths={}; expected={}; manifest_checks=[]
    accepted=json.loads((local/'expected_accepted_CPU_hashes.json').read_text())
    for name,digest in accepted.items():
        p=validated/name; actual=sha(p)
        if actual!=digest or not json.loads(p.read_text())['passed']: raise RuntimeError('Accepted CPU record changed or failed: '+name)
        paths[str(p)]='accepted_CPU_evidence'; expected[str(p)]=(digest,p.stat().st_size,None)
    for name,digest in json.loads((local/'expected_manifest_hashes.json').read_text()).items():
        p=validated/'R2_source_provenance_captured_local.json' if name=='R2_source_provenance.json' else SETUP/name
        actual=sha(p); manifest_checks.append({'path':str(p),'expected_sha256':digest,'actual_sha256':actual,'passed':actual==digest})
        if actual!=digest: raise RuntimeError('Approved manifest drift: '+name)
        paths[str(p)]='historical_manifest'; expected[str(p)]=(digest,p.stat().st_size,None)
    amend=json.loads((SETUP/'R2_storage_manifest_amendment.json').read_text()); groups={}; source_copy_count=0
    for name in ['R2_payload_manifest.json','R2_project_code_manifest.json']:
        items=json.loads((SETUP/name).read_text()); groups[name]=len(items)
        for r in items:
            p=ROOT/r['path']; digest=r['sha256']; size=r['bytes']
            if r['path']==amend['path']: digest=amend['expected_current_sha256']; size=amend['expected_current_bytes']
            key=str(p); prior=expected.get(key)
            if prior and prior[:2]!=(digest,size): raise RuntimeError('Conflicting approved hashes: '+key)
            paths[key]=name; expected[key]=(digest,size,None)
            if r['path'].startswith('baselines/droid_w/upstream/'):
                q=BUILD/r['path'].removeprefix('baselines/droid_w/upstream/')
                paths[str(q)]='system_build_source'; expected[str(q)]=(r['sha256'],r['bytes'],None); source_copy_count+=1
    weights=json.loads((validated/'R2_final_weight_integrity.json').read_text())['weights']
    if len(weights)!=4: raise RuntimeError('Expected four approved weights')
    for r in weights:
        paths[r['path']]='weight_bytes_not_deserialized'; expected[r['path']]=(r['expected_sha256'],r['expected_bytes'],r['real_path'])
    for p in build.rglob('*'):
        if p.is_file(): paths[str(p)]='accepted_CPU_evidence'
    paths[str(latest_path)]='accepted_CPU_pointer'
    for r in json.loads((validated/'R2_installed_extension_integrity.json').read_text())['artifacts']:
        p=pathlib.Path(r['installed_path']); paths[str(p)]='installed_extension'; expected[str(p)]=(r['installed_sha256'],p.stat().st_size,None)
        p=pathlib.Path(r['wheel']); paths[str(p)]='accepted_wheel'; expected[str(p)]=(r['wheel_sha256'],p.stat().st_size,None)
    for name in ['GameCam-WW-V5_7-NA-K6-A-GPU-R1','GameCam-WW-V5_7-NA-K6-A-GPU-R1-MEM','GameCam-WW-V5_7-NA-K6-A-R2-PIN','GameCam-WW-V5_7-NA-K4','GameCam-WW-V5_7-NA-K5_1']:
        directory=ROOT/name
        for p in directory.rglob('*'):
            if p.is_file(): paths.setdefault(str(p),'protected_history')
    # This phase writes only to setup/gpu_preflight_20261108, outside the project.
    for p in ROOT.rglob('*'):
        if p.is_file(): paths.setdefault(str(p),'all_uploaded_project_files')
    site=pathlib.Path('/opt/gamecam/envs/droidw-cu126/lib/python3.10/site-packages')
    for name in ['torch_scatter','xformers']:
        for p in (site/name).rglob('*.so'): paths[str(p)]='additional_runtime_binary'
    rows=[]; mismatches=[]
    for name,group in sorted(paths.items()):
        p=pathlib.Path(name)
        if not p.is_file(): raise RuntimeError('Protected file missing: '+name)
        r={'path':name,'group':group,'bytes':p.stat().st_size,'sha256':sha(p),'real_path':str(p.resolve())}
        if name in expected:
            digest,size,real=expected[name]; r['approved_expected_sha256']=digest
            r['approved_expected_bytes']=size; r['approved_expected_real_path']=real
            r['approved_contract_matches']=r['sha256']==digest and r['bytes']==size and (real is None or real==r['real_path'])
            if not r['approved_contract_matches']: mismatches.append(r)
        rows.append(r)
    return {'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'latest_CPU_pointer':latest,'manifest_row_counts':groups,'approved_manifest_checks':manifest_checks,'system_build_source_files_checked':source_copy_count,'weights_checked':len(weights),'approved_contract_checks':len(expected),'approved_contract_mismatches':mismatches,'files_checked':len(rows),'files':rows,'checkpoint_deserialized':False,'GT_values_read':False,'hash_scope_note':'Raw byte SHA only, including any archived evaluation artifacts; no image decode, trajectory parse, GT use, or weight deserialization. Historical artifacts outside the uploaded payload are not claimed protected.','passed':not mismatches}
if __name__=='__main__':
    out=pathlib.Path(sys.argv[1]); data=capture()
    with out.open('x') as f: json.dump(data,f,indent=2)
    print(json.dumps({'snapshot_files':len(data['files']),'passed':data['passed'],'output':str(out)}))
    raise SystemExit(0 if data['passed'] else 2)