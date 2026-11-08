"""CPU-only audit of frozen Linux paths, symlink targets and content hashes."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import stat

PROJECT_ALIAS = Path('/mnt/d/aaa/GameCam-VO')
PROJECT_REAL = Path('/root/rivermind-data/gamecam/GameCam-VO')

def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def within(path, root):
    try:
        Path(path).relative_to(Path(root))
        return True
    except ValueError:
        return False

def allowed_root(path):
    parts = Path(path).relative_to(PROJECT_ALIAS).parts
    if parts[:3] == ('data', 'sota_assets', 'DROID_W'):
        suffix = Path('data/sota_assets/DROID_W')
    elif parts and parts[0] == 'GameCam-WW-V5_7-NA-K4':
        if 'V56_01' in parts and 'middle' in parts:
            suffix = Path('GameCam-WW-V5_7-NA-K4/inputs/512x288/V56_01/middle')
            if 'rgb' in parts:
                suffix /= 'rgb'
        else:
            suffix = Path('GameCam-WW-V5_7-NA-K4')
    elif parts[:4] in (('baselines', 'droid_w', 'prior_sources', 'FiT3D'), ('baselines', 'droid_w', 'prior_sources', 'Metric3D')):
        suffix = Path(*parts[:4])
    elif parts[:3] == ('baselines', 'droid_w', 'upstream'):
        suffix = Path(*parts[:3])
    elif parts and (parts[0].startswith('GameCam-WW-V5_7-NA-K6-A-R2-') or parts[0] in ('GameCam-WW-V5_7-NA-K6-A-GPU-R1', 'GameCam-WW-V5_7-NA-K5_1')):
        suffix = Path(parts[0])
    else:
        suffix = Path('.')
    return PROJECT_REAL / suffix

def symlink_chain(path):
    current, links = Path(path.anchor), []
    for part in Path(path).parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except OSError:
            break
        if stat.S_ISLNK(info.st_mode):
            links.append({'link': str(current), 'target_text': os.readlink(current),
                          'resolved_target': str(current.resolve(strict=True))})
    return links

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    source, out = Path(args.source_root), Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    spec = json.loads((source / 'config/dependency_pins.json').read_text())
    records = {}

    def add(path, role, real='', size='', digest=''):
        if not path:
            return
        key = str(path)
        item = records.setdefault(key, {'path_linux': key, 'roles': set(), 'real': set(), 'sizes': set(), 'hashes': set()})
        item['roles'].add(role)
        if real:
            item['real'].add(str(real))
        if size not in ('', None):
            item['sizes'].add(int(size))
        if digest:
            item['hashes'].add(str(digest))

    add(PROJECT_ALIAS, 'project_data_root', PROJECT_REAL)
    add(source, 'runtime_pin_root', source.resolve(strict=True))
    for key in ('config', 'k4_live_contract'):
        row = spec[key]
        add(row['path_linux'], key, row.get('real_linux'), row.get('bytes'), row.get('sha256'))
    for row in spec.get('weights', []):
        add(row['path_linux'], 'weight:' + row['id'], row.get('real_linux'), row.get('bytes'), row.get('sha256'))
    hf = spec.get('hf', {})
    add(hf.get('ref_path_linux'), 'hf_revision_ref', hf.get('ref_real_linux'), hf.get('ref_bytes'), hf.get('ref_sha256'))
    for name, row in spec.get('files', {}).items():
        add(source / row['path'], 'frozen_runtime_file:' + name, size=row.get('bytes'), digest=row.get('sha256'))
    for name, value in spec.get('environment', {}).items():
        if isinstance(value, str) and value.startswith('/mnt/'):
            add(value, 'environment:' + name)
    for name, value in spec.get('hub_models', {}).items():
        add(value, 'hub_model:' + name)

    config = source / 'config'
    with (config / 'k4_input_frames.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            add(row.get('path_linux'), 'k4_input_frame:' + str(row.get('published_frame_index')),
                size=row.get('bytes'), digest=row.get('png_sha256'))
    cases = json.loads((config / 'cases.json').read_text(encoding='utf-8-sig'))
    for case in cases:
        add(case.get('rgb_folder_linux'), 'case_rgb_directory:' + str(case.get('case_id')))
        for frame in case.get('frames', []):
            add(frame.get('path_linux'), 'case_frame:' + str(frame.get('frame')), digest=frame.get('png_sha256'))
    for name in ('frozen_weight_manifest.csv', 'inherited_external_dependency_manifest.csv', 'external_dependency_manifest.csv'):
        with (config / name).open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                ident = row.get('id') or row.get('dependency_id') or 'row'
                digest = row.get('expected_sha256') or row.get('sha256')
                add(row.get('path_linux'), 'manifest:' + name + ':' + ident, row.get('real_linux'), row.get('bytes'), digest)
                add(row.get('real_linux'), 'manifest_real:' + name + ':' + ident, size=row.get('bytes'), digest=digest)

    rows, chains = [], {}
    for item in sorted(records.values(), key=lambda x: x['path_linux']):
        path = Path(item['path_linux'])
        declared = sorted(item['real'])
        sizes, hashes = sorted(item['sizes']), sorted(item['hashes'])
        allowed = allowed_root(path) if within(path, PROJECT_ALIAS) else PROJECT_REAL
        row = {'path_linux': str(path), 'declared_real_linux': '|'.join(declared), 'resolved_path_linux': '',
               'exists': False, 'absolute': path.is_absolute(), 'allowed_real_root_linux': str(allowed),
               'within_allowed_root': False, 'device': '', 'inode': '', 'file_type': '', 'bytes': '', 'sha256': '',
               'expected_bytes': '|'.join(map(str, sizes)), 'expected_sha256': '|'.join(hashes),
               'bytes_match': '', 'sha_match': '', 'declared_real_matches_resolved': '',
               'roles': '|'.join(sorted(item['roles'])), 'symlink_chain_json': '', 'status': '', 'error': ''}
        try:
            if not path.is_absolute():
                raise ValueError('PATH_NOT_ABSOLUTE')
            resolved, info = path.resolve(strict=True), path.stat()
            row.update(exists=True, resolved_path_linux=str(resolved), within_allowed_root=within(resolved, allowed),
                       device=info.st_dev, inode=info.st_ino,
                       file_type='directory' if stat.S_ISDIR(info.st_mode) else 'regular_file' if stat.S_ISREG(info.st_mode) else 'other',
                       bytes=info.st_size if stat.S_ISREG(info.st_mode) else '')
            chain = symlink_chain(path)
            row['symlink_chain_json'] = json.dumps(chain, sort_keys=True)
            chains[str(path)] = chain
            row['declared_real_matches_resolved'] = not declared or declared == [str(resolved)]
            if stat.S_ISREG(info.st_mode):
                row['sha256'] = sha256_file(path)
            row['bytes_match'] = not sizes or info.st_size in sizes
            row['sha_match'] = not hashes or row['sha256'] in hashes
            row['status'] = 'PASS' if all((row['within_allowed_root'], row['bytes_match'], row['sha_match'], row['declared_real_matches_resolved'])) else 'REVIEW_REQUIRED'
        except Exception as exc:
            row['status'], row['error'] = 'MISSING_OR_INVALID', type(exc).__name__ + ': ' + str(exc)
        rows.append(row)

    fields = list(rows[0])
    with (out / 'PATH_01_all_path_identity_audit.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    summary = {'source_root_alias': str(source), 'source_root_resolved': str(source.resolve(strict=True)),
               'project_alias': str(PROJECT_ALIAS), 'project_canonical': str(PROJECT_REAL),
               'audited_unique_paths': len(rows), 'pass': sum(x['status']=='PASS' for x in rows),
               'review_required': sum(x['status']=='REVIEW_REQUIRED' for x in rows),
               'missing_or_invalid': sum(x['status']=='MISSING_OR_INVALID' for x in rows),
               'symlink_chains': chains, 'gpu_used': False, 'torch_imported': False,
               'checkpoint_deserialized': False, 'image_decoded': False}
    (out / 'PATH_02_symlink_chain_audit.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k!='symlink_chains'}))

if __name__ == '__main__':
    main()
