"""Read-only transfer of sealed native regressions, without remote archive space."""
import hashlib, json, shlex, subprocess, tarfile
from pathlib import Path

from common import TASK, dump, sha
from remote_transport import SSH, options

REMOTE = '/root/rivermind-data/'
SOURCES = {
    'formal_native_regression': REMOTE+'GAMECAM_TASK011B_20261127_AMP_NATIVE_R2/native_regression',
    'pilot_native_regression': REMOTE+'GAMECAM_TASK011B_20261127_R1/native_regression',
    'precision_audit': REMOTE+'GAMECAM_TASK011B_20261127_R1/precision_audit_001',
    'engineering_attempts': REMOTE+'GAMECAM_TASK011B_20261127_R1/engineering_attempts',
}


def command(code):
    return [str(SSH), '-T', '-p', '31454', *options(),
            'root@sc01-ssh.gpuhome.cc', '/usr/bin/python3 -c '+shlex.quote(code)]


def main():
    parent = TASK/'diagnostics/native_001'
    parent.mkdir(parents=True, exist_ok=True)
    for name, root in SOURCES.items():
        receipt = parent/(name+'_TRANSFER.json')
        if receipt.exists():
            print('ALREADY_VERIFIED', name, flush=True)
            continue
        code = '''import json,hashlib
from pathlib import Path
r=Path(ROOT)
rows=[]
for p in sorted(r.rglob('*')):
 if p.is_file() and not p.is_symlink():
  rows.append(dict(path=str(p.relative_to(r)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
print(json.dumps(rows))
'''.replace('ROOT', repr(root))
        result = subprocess.run(command(code), capture_output=True, timeout=120)
        if result.returncode:
            raise RuntimeError('Read-only diagnostic inventory failed: '+name)
        rows = json.loads(result.stdout)
        if not rows:
            raise RuntimeError('Missing diagnostic evidence: '+name)
        dump(parent/(name+'_SOURCE_SHA256.json'), dict(root=root, files=rows))
        archive = parent/(name+'.tar.gz')
        code = '''import sys,tarfile
from pathlib import Path
r=Path(ROOT)
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as t:
 for name in NAMES:
  p=r/name
  assert p.resolve().is_relative_to(r.resolve()) and p.is_file() and not p.is_symlink()
  t.add(p,arcname=name,recursive=False)
'''.replace('ROOT', repr(root)).replace('NAMES', repr([r['path'] for r in rows]))
        with archive.open('xb') as f:
            result = subprocess.run(command(code), stdout=f, stderr=subprocess.PIPE, timeout=900)
        if result.returncode:
            raise RuntimeError('Diagnostic stream failed; preserve partial archive: '+name)
        dest = parent/name
        dest.mkdir(exist_ok=False)
        with tarfile.open(archive, 'r:gz') as t:
            for item in t:
                target = (dest/item.name).resolve()
                if not target.is_relative_to(dest.resolve()) or not item.isfile() or item.issym() or item.islnk():
                    raise RuntimeError('Unsafe diagnostic member')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(t.extractfile(item).read())
        for row in rows:
            p=dest/row['path']
            if p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:
                raise RuntimeError('Diagnostic transfer SHA mismatch')
        dump(receipt, dict(status='PASS', source=root, files=len(rows),
            archive_sha256=sha(archive), archive_bytes=archive.stat().st_size,
            original_remote_files_unchanged=True, remote_archive_created=False))
        print('SEALED_DIAGNOSTICS_VERIFIED', name, len(rows), archive.stat().st_size, flush=True)


if __name__=='__main__':
    main()
