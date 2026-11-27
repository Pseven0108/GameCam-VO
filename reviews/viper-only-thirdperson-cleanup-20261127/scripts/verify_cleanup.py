"""Validate exact identities before deletion and protected evidence afterwards."""
from pathlib import Path
import gzip,hashlib,json,shutil,sys,time

OUT=Path(__file__).resolve().parent
phase=sys.argv[1]
plan_path=OUT/'EXTENDED_DELETION_PLAN.json'
plan=json.loads(plan_path.read_text(encoding='utf-8'))
protected=json.loads((OUT/'PROTECTED_BEFORE.json').read_text(encoding='utf-8'))
errors=[];checked=0
if phase=='before':
    with gzip.open(OUT/'EXTENDED_FILE_IDENTITIES.json.gz','rt',encoding='utf-8') as f:records=json.load(f)
    for r in records:
        p=Path(r['path'])
        try:s=p.lstat()
        except OSError:errors.append({'path':str(p),'error':'MISSING_OR_INACCESSIBLE'});continue
        if (s.st_size,s.st_mtime_ns,s.st_ino,s.st_dev)!=(r['bytes'],r['mtime_ns'],r['inode'],r['device']):errors.append({'path':str(p),'error':'IDENTITY_CHANGED'})
        checked+=1
    result={'status':'PASS' if not errors else 'FAIL','phase':phase,'file_identities_checked':checked,'plan_sha256':hashlib.sha256(plan_path.read_bytes()).hexdigest(),'errors':errors}
    (OUT/'PREDELETE_IDENTITY_CHECK.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
else:
    for r in protected:
        p=Path(r['path'])
        try:s=p.lstat()
        except OSError:errors.append({'path':str(p),'error':'PROTECTED_PATH_MISSING'});continue
        if (s.st_size,s.st_mtime_ns,s.st_ino,s.st_dev)!=(r['bytes'],r['mtime_ns'],r['inode'],r['device']):errors.append({'path':str(p),'error':'PROTECTED_IDENTITY_CHANGED'})
        if 'sha256' in r and hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:errors.append({'path':str(p),'error':'PROTECTED_SHA_CHANGED'})
        checked+=1
    remaining=[t['path'] for t in plan['targets'] if Path(t['path']).exists()]
    result={'status':'PASS' if not errors and not remaining else 'FAIL','phase':phase,'protected_files_checked':checked,'protected_small_files_sha256_checked':sum('sha256' in r for r in protected),'remaining_deletion_targets':remaining,'volume_after':{v:dict(zip(['total','used','free'],shutil.disk_usage(v))) for v in ['C:/','D:/']},'errors':errors,'no_model_or_GPU_execution':True}
    result['free_space_increase_bytes']={v:result['volume_after'][v]['free']-plan['volume_before'][v]['free'] for v in ['C:/','D:/']}
    (OUT/'POSTDELETE_PROTECTION_CHECK.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['errors']},ensure_ascii=False,indent=2))
if errors:print('ERROR_COUNT',len(errors))
if result['status']!='PASS':raise SystemExit(1)
