"""Seal attempt files and verify a distinct receiving copy. No cleanup operation."""
import json
import os
import shutil
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

from contracts import need, stat_sha, stream_sha, strict_json

MANIFEST = '_TASK004A_ARCHIVE_MANIFEST.json'


def file_entry(path):
    return dict(bytes=path.stat().st_size, sha256=stat_sha(path))


def inventory(root):
    root = Path(root)
    need(root.is_dir() and not root.is_symlink(), 'archive source must be a real directory')
    files = {}
    for directory, dirs, names in os.walk(root, followlinks=False):
        directory = Path(directory)
        for child in (*dirs, *names):
            path = directory / child
            st = path.lstat()
            need(not path.is_symlink() and not getattr(st, 'st_file_attributes', 0) & 0x400,
                 f'linked archive member: {path}')
        for name in names:
            path = directory / name
            key = path.relative_to(root).as_posix()
            need(path.is_file() and key != MANIFEST and '\\' not in key and ':' not in key,
                 f'invalid archive member: {key}')
            files[key] = file_entry(path)
    need(bool(files), 'cannot seal an empty attempt')
    return dict(sorted(files.items()))


def verify_zip(path, *, expected_sha=None, expected_attempt=None):
    path = Path(path)
    sha = stat_sha(path)
    if expected_sha is not None:
        need(sha == expected_sha, 'receiving ZIP SHA-256 mismatch')
    with ZipFile(path) as z:
        names = z.namelist()
        need(len(names) == len(set(names)) == len({n.casefold() for n in names}), 'duplicate archive member')
        for name in names:
            parts = PurePosixPath(name).parts
            need(parts and not name.startswith('/') and not name.endswith('/')
                 and '..' not in parts and '\\' not in name and ':' not in name
                 and name == '/'.join(parts), 'unsafe archive member')
        doc = strict_json(z.read(MANIFEST))
        need(doc['schema'] == 'GAMECAM_TASK004A_ATTEMPT_ARCHIVE_V1'
             and set(names) == set(doc['files']) | {MANIFEST}, 'attempt manifest coverage mismatch')
        if expected_attempt is not None:
            need(doc['attempt_id'] == expected_attempt, 'wrong attempt archive')
        # Reading each member to EOF also verifies its ZIP CRC.
        for member, entry in doc['files'].items():
            need(z.getinfo(member).file_size == entry['bytes'], f'{member}: ZIP size mismatch')
            with z.open(member) as stream:
                need(stream_sha(stream) == entry['sha256'],
                     f'{member}: ZIP payload SHA mismatch')
    return dict(attempt_id=doc['attempt_id'], path=str(path.resolve()), bytes=path.stat().st_size,
                sha256=sha, crc='PASS', payload_matches=len(doc['files']), files=doc['files'])


def seal(root, path, attempt_id):
    root, path = Path(root), Path(path)
    need(not path.resolve().is_relative_to(root.resolve()), 'archive output must be outside attempt files')
    payload = inventory(root)
    with ZipFile(path, 'x', ZIP_DEFLATED, compresslevel=1, allowZip64=True) as z:
        for name in payload:
            z.write(root / name, name)
        z.writestr(MANIFEST, json.dumps(dict(schema='GAMECAM_TASK004A_ATTEMPT_ARCHIVE_V1',
                                          attempt_id=attempt_id, files=payload), sort_keys=True))
    receipt = verify_zip(path, expected_attempt=attempt_id)
    need(inventory(root) == payload == receipt['files'], 'source changed during sealing')
    return receipt


def receive_copy(source, destination, receipt):
    source, destination = Path(source), Path(destination)
    need(source.resolve() != destination.resolve(), 'copy destination is not independent')
    with source.open('rb') as stream, destination.open('xb') as copy:
        shutil.copyfileobj(stream, copy, 2**20)
        copy.flush()
        os.fsync(copy.fileno())
    received = verify_zip(destination, expected_sha=receipt['sha256'], expected_attempt=receipt['attempt_id'])
    need(received['files'] == receipt['files'], 'receiving inventory mismatch')
    return dict(status='VERIFIED_COPY', source=receipt, received=received, cleanup_authorized=False)
