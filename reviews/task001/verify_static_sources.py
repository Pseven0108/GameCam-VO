"""Verify frozen source and result receipts using the standard library only."""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
import zipfile


OUT = Path(__file__).resolve().parent
EXP = OUT.parent
PRIOR = EXP / 'DROID_SLAM_TO_DROID_W_SOURCE_DIFF_EVIDENCE_MAPPING_R1'
MATCHED = EXP / 'VIPER_MATCHED_DUAL_BASELINE_R2'
SEGMENT = 'val_007_full_00001-00487'
PINS = {
    'DROID-SLAM': '2dfd39f0dcad44012ca7bbb8aa70b55edbfa9c99',
    'DROID-W': 'c3414af6047d06bafc1a6645d09f23247f3b2cdc',
}


def check(ok, label):
    if not ok:
        raise ValueError(label)


def sha256(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def git_oid(kind, data):
    return hashlib.sha1(f'{kind} {len(data)}\0'.encode() + data).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def tree_oid(entries):
    children = defaultdict(dict)
    for path, r in entries.items():
        parts = PurePosixPath(path).parts
        check(parts and all(p not in ('..', '/', '.') for p in parts), path)
        for i in range(len(parts) - 1):
            children[parts[:i]][parts[i]] = ('40000', None)
        children[parts[:-1]][parts[-1]] = (r['mode'], r['sha'])

    def digest(parts):
        items = children[parts]
        # Git orders directories as if their names had a trailing slash.
        names = sorted(items, key=lambda n: (n + ('/' if items[n][1] is None else '')).encode())
        buf = bytearray()
        for n in names:
            mode, oid = items[n]
            buf.extend(f'{mode} {n}\0'.encode())
            buf.extend(bytes.fromhex(oid if oid else digest(parts + (n,))))
        return git_oid('tree', bytes(buf))

    return digest(())


def verify_repo(name, commit, hist, lock, checks):
    root = PRIOR / 'sources' / name
    archive = PRIOR / 'inputs' / f'{name}-{commit[:12]}.tar.gz'
    tree = load(PRIOR / 'inputs' / f'{name}-{commit[:12]}-tree.json')
    entries = {r['path']: r for r in tree['tree'] if r['type'] != 'tree'}
    identity = lambda r: (r['mode'], r['type'], r['sha'])
    check(not tree['truncated'] and tree['sha'] == commit, f'{name} tree receipt')
    check({p: identity(r) for p, r in entries.items()} ==
          {r['path']: identity(r) for r in hist['tree']}, f'{name} historical tree')
    raw = hist['commit_object'].encode('utf-8')
    check(git_oid('commit', raw) == hist['intake_head'] == commit, f'{name} commit object')
    root_oid = raw.splitlines()[0].removeprefix(b'tree ').decode('ascii')
    check(tree_oid(entries) == root_oid, f'{name} reconstructed tree object')
    archive_sha = sha256(archive)
    check(archive_sha == lock['archive_sha256'] == hist['archive']['sha256'], f'{name} archive SHA-256')
    check(archive.stat().st_size == hist['archive']['bytes'], f'{name} archive length')
    blobs = {p for p, r in entries.items() if r['type'] == 'blob'}
    links = {p for p, r in entries.items() if r['type'] == 'commit' and r['mode'] == '160000'}
    check(blobs | links == set(entries), f'{name} entry types')
    check(root.is_dir() and not (root / '.git').exists(), f'{name} expected snapshot without .git')
    local = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() or p.is_symlink()}
    check(local == blobs, f'{name} local payload set: {sorted(local ^ blobs)}')
    with tarfile.open(archive, 'r:gz') as tar:
        members = {}
        for m in tar.getmembers():
            if m.isdir():
                continue
            prefix, _, path = m.name.partition('/')
            check(prefix == f'{name}-{commit}' and path not in members, m.name)
            members[path] = m
        check(set(members) == blobs, f'{name} archive payload set: {sorted(set(members) ^ blobs)}')
        for path, r in sorted(entries.items()):
            if path in links:
                checks.append([name, path, r['mode'], r['sha'], '', 'GITLINK_POINTER_VERIFIED_ONLY'])
                continue
            m, p = members[path], root / path
            if r['mode'] == '120000':
                check(m.issym(), path)
                archived = m.linkname.encode()
                data = os.readlink(p).encode() if p.is_symlink() else p.read_bytes()
            else:
                check(m.isfile() and bool(m.mode & 0o111) == (r['mode'] == '100755'), f'{path} mode')
                with tar.extractfile(m) as f:
                    archived = f.read()
                data = p.read_bytes()
            check(data == archived and len(data) == r['size'] and git_oid('blob', data) == r['sha'], f'{name} blob {path}')
            checks.append([name, path, r['mode'], r['sha'], len(data), 'ARCHIVE_AND_SNAPSHOT_BLOB_VERIFIED'])
    print(f'{name}: {len(blobs)} archive/snapshot blobs + {len(links)} gitlinks; Git commit/tree verified')
    return entries, dict(
        repository=lock['repository'], commit=commit, tree_sha1=root_oid, snapshot=str(root),
        local_branch=None, local_worktree_kind='EXTRACTED_ARCHIVE_NO_GIT',
        archive=str(archive), archive_sha256=archive_sha, archive_bytes=archive.stat().st_size,
        tracked_entries=len(entries), blobs_verified=len(blobs), gitlink_pointers_verified=len(links),
        recursive_dependency_equivalence_verified=False, historical_intake_path=hist['intake_path'],
        historical_intake_head=hist['intake_head'], historical_intake_branch='NOT_RECORDED_IN_INVENTORY',
        historical_intake_status_rows=len(hist['intake_status']), historical_deployed_tracked_changes=len(hist['deployed_changes']),
        stale_gitmodules_entries=lock.get('stale_gitmodule_entries', []), current_server_checked=False,
    )


def verify_ledgers(trees):
    master, symbols = rows(PRIOR / 'SOURCE_DIFF_MASTER.csv'), rows(PRIOR / 'FUNCTION_DIFF_LEDGER.csv')
    used = {name: set() for name in PINS}
    pairs = set()
    columns = (('DROID-SLAM', 'original'), ('DROID-W', 'droid_w'))
    for r in master:
        a, b = r['original_path'], r['droid_w_path']
        pairs.add((a, b))
        for repo, col in columns:
            path = r[f'{col}_path']
            if path:
                check(path not in used[repo], f'duplicate ledger path {repo}:{path}')
                used[repo].add(path)
                entry = trees[repo][path]
                check((entry['sha'], entry['mode']) == (r[f'{col}_git_sha1'], r[f'{col}_mode']), f'ledger identity {path}')
        equal = r['original_git_sha1'] == r['droid_w_git_sha1'] and r['original_mode'] == r['droid_w_mode']
        status = ('ADDED' if not a else 'DELETED' if not b else
                  ('UNCHANGED' if equal else 'MODIFIED') if a == b else
                  ('RELOCATED_IDENTICAL' if equal else 'RELOCATED_MODIFIED'))
        check(r['change'] == status, f'ledger classification {a} / {b}')
    check(all(used[repo] == set(trees[repo]) for repo in PINS), 'ledger coverage')
    line_counts = {}
    for r in symbols:
        check((r['original_path'], r['droid_w_path']) in pairs, f'symbol file pair {r["symbol"]}')
        for repo, col in columns:
            span = r[f'{col}_lines']
            if span:
                key = (repo, r[f'{col}_path'])
                if key not in line_counts:
                    line_counts[key] = len((PRIOR / 'sources' / repo / key[1]).read_text(encoding='utf-8-sig').splitlines())
                start, stop = map(int, span.split('-'))
                check(1 <= start <= stop <= line_counts[key], f'symbol bounds {key}:{span}')
    print(f'File ledger: {len(master)} rows, complete coverage; symbol ledger: {len(symbols)} rows, spans in bounds')
    return dict(file_rows=len(master), file_status=Counter(r['change'] for r in master),
                symbol_rows=len(symbols), symbol_status=Counter(r['status'] for r in symbols),
                symbol_scope='Historical AST/lexical index; current checks cover file pairs and line bounds.')


def verify_receipts():
    export = {
        'SOURCE_DIFF_MASTER.csv': PRIOR / 'SOURCE_DIFF_MASTER.csv',
        'FUNCTION_DIFF_LEDGER.csv': PRIOR / 'FUNCTION_DIFF_LEDGER.csv',
        'MATCHED_R2_VAL007_LOCAL_DISPLACEMENT.csv': MATCHED / 'evaluation/VAL007_LOCAL_DISPLACEMENT.csv',
    }
    manifest = {r['path']: r for r in rows(PRIOR / 'SHA256_MANIFEST.csv')}
    prior_paths = ('SOURCE_DIFF_MASTER.csv', 'FUNCTION_DIFF_LEDGER.csv',
                   'evidence/SERVER_READ_ONLY_INVENTORY.json', 'inputs/official-source-lock.json')
    receipts = []

    def fingerprint(p, scope):
        item = [str(p), p.stat().st_size, sha256(p), scope]
        receipts.append(item)
        return item[1:3]

    for rel in prior_paths:
        size, digest = fingerprint(PRIOR / rel, 'HISTORICAL_SOURCE_AUDIT_SHA256_MANIFEST_MATCH')
        check(digest == manifest[rel]['sha256'] and size == int(manifest[rel]['bytes']), f'historical digest {rel}')
    patch = PRIOR / 'evidence/OFFICIAL_TEXT_DIFF.patch'
    ref, = (r for r in load(PRIOR / 'evidence/EXTERNAL_ARTIFACT_REFERENCES.json')['local_artifacts']
            if Path(r['path']) == patch)
    size, digest = fingerprint(patch, 'HISTORICAL_EXTERNAL_ARTIFACT_REFERENCE_MATCH')
    check((size, digest) == (ref['bytes'], ref['sha256']), 'historical large patch identity')

    files = ('BASELINE_VERSION_AUDIT.md', 'INPUT_PAIRING_AUDIT.md', 'FINAL_REVIEW.md',
             'VAL007_LOCAL_DISPLACEMENT.csv', 'PAIRED_SEGMENT_COMPARISON.csv', 'REVIEW_STATUS.json')
    arc = MATCHED / 'evaluation/VIPER_MATCHED_DUAL_BASELINE_R2_REVIEW_PACKAGE.zip'
    _, digest = fingerprint(arc, 'MATCHED_R2_ZIP_SIDECAR_AND_CRC_MATCH')
    check(digest == arc.with_suffix('.zip.sha256').read_text(encoding='utf-8-sig').split()[0], 'matched R2 archive SHA-256')
    with zipfile.ZipFile(arc) as z:
        check(z.testzip() is None, 'matched R2 archive CRC')
        for name in files:
            rel = f'evaluation/{name}'
            p = MATCHED / rel
            check(p.read_bytes() == z.read(rel), f'archive/local report mismatch {rel}')
            fingerprint(p, 'MATCHED_R2_FINAL_SEALED_ZIP_BYTES_MATCH')
    status = load(MATCHED / 'evaluation/REVIEW_STATUS.json')
    check(status['status'] == 'COMPLETE' and status['score_pairs'] == 92 and status['sequences'] == 47
          and status['frames'] == 49815, 'matched R2 final counts')
    paired = rows(MATCHED / 'evaluation/PAIRED_SEGMENT_COMPARISON.csv')
    case, = (r for r in paired if r['segment'] == SEGMENT)
    check(len(paired) == len({r['segment'] for r in paired}) == 92
          and all(r['paired_scored'].lower() == 'true' for r in paired), 'matched R2 pairing ledger')
    o = MATCHED / 'results' / SEGMENT / 'attempt_001/model_config.json'
    w = MATCHED / 'wild_reference' / SEGMENT / 'attempt.json'
    wi = w.with_name('model_input.json')
    orig, wild, wild_inputs = load(o), load(w), load(wi)
    check(orig['upstream_commit'] == PINS['DROID-SLAM'] and wild['upstream_commit'] == PINS['DROID-W']
          and orig['input_manifest_sha256'] == wild['input_manifest_sha256']
          and orig['stride'] == wild['stride'] == 1 and not orig['asynchronous']
          and orig['supplied_pose_rows'] == 0 and orig['input_rgb_ids'] == list(range(1, 488))
          and wild['input_frames'] == 487 and wild_inputs['rgb_ids'] == orig['input_rgb_ids']
          and wild_inputs['actual_loader_k'] == orig['effective_k']
          and wild_inputs['manifest_sha256'] == orig['input_manifest_sha256'], 'matched R2 val_007 native identity')
    for p in (o, w, w.with_name('native_config.yaml'), wi,
              MATCHED / 'pipeline/run_original.py'):
        fingerprint(p, 'TASK001_LOCAL_READ_FINGERPRINT')
    print(f'Matched R2 stride=1: {len(paired)} scored segment pairs; archived reports CRC/SHA-256 verified')
    return export, receipts, dict(
        final_status=status['status'], pairs=len(paired), sequences=status['sequences'],
        frames=status['frames'], segment=case, stride=1, input_manifest_sha256=orig['input_manifest_sha256'],
        matched_outside_stride1_results_used=False,
    )


def write_csv(path, headers, data):
    with path.open('x', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', action='store_true', help='Create new evidence files in this directory.')
    record = parser.parse_args().record
    inventory = load(PRIOR / 'evidence/SERVER_READ_ONLY_INVENTORY.json')['repositories']
    locks = {r['path']: r for r in load(PRIOR / 'inputs/official-source-lock.json')}
    checks, trees, repos = [], {}, {}
    for name, commit in PINS.items():
        trees[name], repos[name] = verify_repo(name, commit, inventory[name], locks[f'source/{name}'], checks)
    ledgers = verify_ledgers(trees)
    exports, fingerprints, matched = verify_receipts()
    if record:
        dest = OUT / 'evidence'
        dest.mkdir(exist_ok=False)
        for name, p in exports.items():
            with (dest / name).open('xb') as f:
                f.write(p.read_bytes())
        write_csv(dest / 'SOURCE_ENTRY_VERIFICATION.csv', ['repository', 'path', 'git_mode', 'git_sha1', 'bytes', 'check'], checks)
        write_csv(dest / 'AUDIT_INPUT_FINGERPRINTS.csv', ['path', 'bytes', 'sha256', 'verification_scope'], fingerprints)
        with (dest / 'SOURCE_IDENTITY_VERIFICATION.json').open('x', encoding='utf-8', newline='\n') as f:
            json.dump(dict(status='PASS', repositories=repos, ledgers=ledgers, matched_r2=matched), f, ensure_ascii=False, indent=2)
            f.write('\n')
    print('PASS: static verification only; no model code executed')


if __name__ == '__main__':
    main()
