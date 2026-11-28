"""Read-only, lossless backup of the two completed A0 snapshots; no torch load."""
import gzip
import hashlib
import json
from pathlib import Path,PurePosixPath
import subprocess
import tarfile
from remote_control import BASE,REMOTE,command

CODE=r'''
from pathlib import Path
import gzip,hashlib,io,json,subprocess,sys,tarfile,time
root=Path(REMOTE);task=root/'repo/experiments/TASK011E'
assert (task/'BATCH_STOPPED.json').is_file()
assert not subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
folder=task/'fixed_state/snapshots/43/val_038_00448-00511'
records=[json.loads(row) for row in (folder/'SNAPSHOT_INDEX.jsonl').read_text().splitlines()]
assert len(records)==2
with gzip.GzipFile(fileobj=sys.stdout.buffer,mode='wb',compresslevel=1,mtime=0) as gz:
    with tarfile.open(fileobj=gz,mode='w|') as archive:
        for record in records:
            path=folder/record['path'];assert path.is_file() and path.stat().st_size==record['bytes']
            # The native collector already computed each raw-file SHA. The
            # receiver independently reconstructs and checks every source byte.
            member=archive.gettarinfo(str(path),arcname=record['path'])
            with path.open('rb') as reader:archive.addfile(member,reader)
        raw=(json.dumps(records,indent=2)+'\n').encode();member=tarfile.TarInfo('SOURCE_SNAPSHOT_INDEX.json')
        member.size=len(raw);archive.addfile(member,io.BytesIO(raw))
'''.replace('REMOTE',repr(REMOTE))


def main():
    backup=Path('D:/aaa/GameCam-VO/server_backups/TASK011E_R3_A0_SNAPSHOTS_20261128')
    backup.mkdir(parents=True,exist_ok=False)
    path=backup/'A0_FULL_INPUT_SNAPSHOTS.tar.gz'
    with path.open('xb') as output,(backup/'TRANSFER_STDERR.txt').open('xb') as error:
        result=subprocess.run(command(CODE),stdout=output,stderr=error,timeout=900,
                              creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise RuntimeError('Keep partial backup, no deletion or replay')
    rows=[]
    with tarfile.open(path,'r:gz') as archive:
        while member:=archive.next():
            rel=PurePosixPath(member.name)
            assert member.isfile() and not rel.is_absolute() and '..' not in rel.parts
            digest=hashlib.sha256();size=0
            with archive.extractfile(member) as reader:
                if member.name=='SOURCE_SNAPSHOT_INDEX.json':
                    expected=json.load(reader);continue
                for block in iter(lambda:reader.read(4*1024**2),b''):
                    digest.update(block);size+=len(block)
            rows.append(dict(path=member.name,bytes=size,sha256=digest.hexdigest()))
    by={row['path']:row for row in expected}
    assert len(rows)==len(by)==2
    for row in rows:
        assert row['bytes']==by[row['path']]['bytes'] and row['sha256']==by[row['path']]['sha256']
    # Read the gzip footer to EOF independently, rather than treating a valid
    # tar end marker as a gzip integrity certificate.
    with gzip.open(path,'rb') as reader:
        for _ in iter(lambda:reader.read(8*1024**2),b''):pass
    digest=hashlib.sha256()
    with path.open('rb') as reader:
        for block in iter(lambda:reader.read(4*1024**2),b''):digest.update(block)
    value=dict(status='PASS',archive=str(path),archive_bytes=path.stat().st_size,
        archive_sha256=digest.hexdigest(),raw_bytes=sum(row['bytes'] for row in rows),
        raw_SHA_verified=rows,gzip_CRC='PASS',remote_sources_modified=False,
        snapshots_deserialized=False,GPU_used=False,
        storage_candidate_only_not_deployed=True)
    (backup/'BACKUP_VERIFICATION.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    (BASE/'SNAPSHOT_COMPRESSION_VERIFICATION.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(value,indent=2))


if __name__=='__main__':main()
