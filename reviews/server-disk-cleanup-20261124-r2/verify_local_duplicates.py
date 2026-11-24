import hashlib,json,pathlib,zipfile,tarfile
root=pathlib.Path(__file__).resolve().parent
c=json.loads((root/'candidates.stdout.json').read_text())
lookup={p.name:p for p in pathlib.Path(r'D:\aaa\GameCam-VO\experiments').rglob('*') if p.is_file() and p.name in {pathlib.PurePosixPath(r['path']).name for r in c['other_archives']}}
matched=[]
for row in c['other_archives']:
    p=lookup.get(pathlib.PurePosixPath(row['path']).name)
    if p is None or p.stat().st_size!=row['bytes']:continue
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    if h.hexdigest()!=row['sha256']:continue
    if p.suffix=='.zip':
        with zipfile.ZipFile(p) as z:assert z.testzip() is None
        integrity='ZIP_CRC_PASS'
    else:
        with tarfile.open(p,'r:*') as t:
            for member in t:
                if member.isfile():
                    with t.extractfile(member) as f:
                        while f.read(8*1024**2):pass
        integrity='TAR_FULL_MEMBER_READ_PASS'
    matched.append({**row,'local_backup':str(p),'local_sha256':h.hexdigest(),'archive_integrity':integrity})
(root/'DUPLICATE_ARCHIVES_LOCAL_VERIFICATION.json').write_text(json.dumps(matched,indent=2))
print(json.dumps({'matched':len(matched),'allocated_GiB':sum(r['allocated'] for r in matched)/2**30,'archives':[{'remote':r['path'],'local':r['local_backup']} for r in matched]},indent=2))
