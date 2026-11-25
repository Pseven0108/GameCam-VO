"""Release validation and packaging, without running new research experiments."""
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DELIVERIES=ROOT/'deliveries'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):
            h.update(part)
    return h.hexdigest()


def write_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def validate():
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':
        raise RuntimeError('Explicit empty CUDA_VISIBLE_DEVICES required')
    before=json.loads((ROOT/'evidence/PRESERVATION_BEFORE.json').read_text(encoding='utf-8'))
    unchanged=[]; tracking=[]; changed=[]
    for entry in before['files']:
        p=Path(entry['path'])
        actual={'path':str(p),'exists':p.is_file()}
        if p.is_file():
            st=p.stat()
            actual.update({'sha256':sha(p),'bytes':st.st_size,'mtime_ns':st.st_mtime_ns})
        if p.name=='TASK006A_PROGRESS.md' and p.parent.name=='docs':
            saved=ROOT/'evidence/FORMAL_PROGRESS_AFTER.md'
            if not p.is_file() or p.read_bytes()!=saved.read_bytes():
                raise RuntimeError('Progress postimage mismatch')
            tracking.append({**actual,'intentional_metadata_update':True,'before_sha256':entry['sha256']})
        elif all(actual.get(k)==entry[k] for k in ('sha256','bytes','mtime_ns')):
            unchanged.append(actual)
        else:
            changed.append({'before':entry,'after':actual})
    write_json(ROOT/'evidence/PRESERVATION_AFTER.json',{
        'protected_unchanged':len(unchanged),'metadata_updates':len(tracking),
        'unexpected_changes':changed,'unchanged_files':unchanged,'authorized_tracking_updates':tracking,
        'pass':not changed,'source_and_R0_history_unchanged':not changed})
    if changed: raise RuntimeError('Protected scientific history changed')
    parsed=[]
    forbidden={'torch','tensorflow','jax','safetensors','transformers','cupy','cv2','droid_backends'}
    for dirname in ('src','tests','tools'):
        for p in sorted((ROOT/dirname).rglob('*.py')):
            tree=ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
            imports=[]
            for node in ast.walk(tree):
                if isinstance(node,ast.Import): imports.extend(n.name for n in node.names)
                if isinstance(node,ast.ImportFrom): imports.append(node.module or '')
            if any(s.split('.')[0] in forbidden for s in imports):
                raise RuntimeError(f'Forbidden research import in {p}')
            parsed.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p),'imports':sorted(set(imports))})
    result=json.loads((ROOT/'results/research_003/RESEARCH_RESULTS.json').read_text(encoding='utf-8'))
    tests=json.loads((ROOT/'results/research_003/UNIT_TEST_REPORT.json').read_text(encoding='utf-8'))
    assert result['success'] and tests['tests_run']==97 and tests['passed']==97
    assert not tests['torch_imported'] and all(x['status']=='PASS' for x in tests['records'])
    assert not (ROOT/'results/research_003/FAILURE.txt').exists()
    receipt=json.loads((ROOT/'logs/RESEARCH_EXECUTION_RECEIPT_003.json').read_text(encoding='utf-8-sig'))
    assert receipt['exit_code']==0
    assert receipt['stdout_sha256']==sha(ROOT/'logs/research_003.stdout.txt')
    assert receipt['stderr_sha256']==sha(ROOT/'logs/research_003.stderr.txt')
    assert (ROOT/'logs/research_003.stderr.txt').stat().st_size==0
    report={'passed':True,'source_AST_files':len(parsed),'parsed_files':parsed,
            'unit_tests_passed':tests['passed'],'research_exit_code':0,
            'execution_output_sha_pass':True,'protected_scientific_files_unchanged':len(unchanged),
            'metadata_updates':len(tracking),'GPU_or_native_equivalence_certified':False}
    write_json(ROOT/'evidence/RELEASE_VALIDATION.json',report)
    return report


def main():
    archive=DELIVERIES/'GAMECAM_TASK006A_R1_CADP_CPU_REVIEW.zip'
    if archive.exists(): raise RuntimeError('Final archive exists; do not overwrite')
    report=validate()
    files=sorted(p for p in ROOT.rglob('*') if p.is_file() and DELIVERIES not in p.parents
                 and '__pycache__' not in p.parts and p.name!='FILE_SHA256_MANIFEST.json')
    manifest={'algorithm':'SHA-256','scope':'All payload files excluding this manifest and deliveries/ self-referential outer artifacts',
              'files':[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]}
    mf=ROOT/'FILE_SHA256_MANIFEST.json'
    if mf.exists(): raise RuntimeError('Payload manifest already exists')
    write_json(mf,manifest)
    files.append(mf)
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(files): z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        bad=z.testzip()
        if bad is not None: raise RuntimeError(f'ZIP CRC failed {bad}')
        inside=json.loads(z.read('FILE_SHA256_MANIFEST.json').decode('utf-8'))
        assert set(z.namelist())==set(x['path'] for x in inside['files'])|{'FILE_SHA256_MANIFEST.json'}
        for entry in inside['files']:
            data=z.read(entry['path'])
            assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
        assert hashlib.sha256(z.read('FILE_SHA256_MANIFEST.json')).hexdigest()==sha(mf)
        members=len(z.namelist())
    archive_hash=sha(archive)
    validation={'archive':archive.name,'bytes':archive.stat().st_size,'members':members,
                'CRC':'PASS','internal_SHA256_entries':len(manifest['files']),'internal_SHA256':'PASS',
                'payload_coverage':'PASS','payload_manifest_sha256':sha(mf),'archive_sha256':archive_hash,
                'release_validation':'PASS','GPU_used':False,'R2_executed':False}
    vr=DELIVERIES/'ZIP_VALIDATION.json'
    write_json(vr,validation)
    (DELIVERIES/(archive.name+'.sha256')).write_text(archive_hash+'  '+archive.name+'\n',encoding='utf-8')
    detached=[mf,archive,vr,DELIVERIES/(archive.name+'.sha256')]
    write_json(DELIVERIES/'DELIVERY_SHA256_MANIFEST.json',{
        'scope':'Detached artifacts and payload manifest; excludes self to avoid circular hash',
        'files':[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in detached]})
    print(json.dumps({'validation':validation,'protected_files':report['protected_scientific_files_unchanged']},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
