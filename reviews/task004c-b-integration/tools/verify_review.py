"""Read-only CRC, member-set and SHA verification for the review ZIP."""
import argparse,hashlib,json,pathlib,zipfile
def verify(path):
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate ZIP members')
        for name in names:
            p=pathlib.PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name:raise ValueError('Unsafe ZIP path')
        bad=z.testzip()
        if bad is not None:raise ValueError('ZIP CRC failed: '+bad)
        manifest=json.loads(z.read('FILE_SHA256_MANIFEST.json'))
        expected=manifest['files']
        if set(names)!=set(expected)|{'FILE_SHA256_MANIFEST.json'}:raise ValueError('Manifest does not cover every non-self member')
        for name,row in expected.items():
            raw=z.read(name)
            if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('SHA/size mismatch: '+name)
    p=pathlib.Path(path);h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return {'ZIP':str(p),'bytes':p.stat().st_size,'members':len(names),'CRC':'PASS','SHA256_entries':len(expected),
            'SHA256_matches':len(expected),'SHA256':'PASS','ZIP_sha256':h.hexdigest(),'manifest_self_reference_excluded':True}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('zip',type=pathlib.Path);a=p.parse_args();print(json.dumps(verify(a.zip),indent=2))
