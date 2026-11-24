"""Package and verify the captured Task 003 evidence; no model imports."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'FILE_SHA256_MANIFEST.json'
ARCHIVE = ROOT / 'GAMECAM_TASK003_VAL007_OBSERVATION_REVIEW.zip'
ENTRANCE = 'README_\u8bf7\u5148\u8bfb.md'
FOLDERS = ('evidence', 'figures', 'logs', 'remote/capture', 'remote/incoming', 'tools')
SUFFIXES = {'.csv', '.diff', '.json', '.jsonl', '.log', '.md', '.png', '.py', '.txt', '.yaml'}
SPECIAL = {'remote/capture/ONE_RUN_CLAIM', 'remote/capture/trajectory.npz'}
ESSENTIAL = {
    ENTRANCE, 'TASK003_FINAL_REVIEW.md', 'EXECUTION_LOG.md',
    'TASK003_KEYFRAME_EVENT_LOG.csv', 'TASK003_FRONTEND_LOCAL_BA_LOG.csv',
    'TASK003_FINAL_BA_ITERATION_LOG.csv', 'TASK003_METRIC_DEPTH_SUMMARY.csv',
    'TASK003_UNCERTAINTY_SUMMARY.csv', 'TASK003_FILLER_UPDATE_LOG.csv',
    'TASK003_VAL007_INTERVAL_ANALYSIS.csv', 'TASK003_312_328_LOCAL_BA_TIMELINE.csv',
    'figures/TASK003_STAGE_DISPLACEMENT.png', 'figures/TASK003_FINAL_TRAJECTORY.png',
    'evidence/TASK003_FINAL_PREFLIGHT.json', 'evidence/TASK003_TARGET_EVENT_CROSSCHECK.json',
    'evidence/RERUN_BROWSER_TRACKING.png', 'evidence/REMOTE_NATIVE_VIDEO_IDENTITY.txt',
    'remote/incoming/native_config.yaml', 'remote/capture/native_config.yaml',
    'remote/incoming/TASK003_INSTRUMENTATION_PATCH.diff', 'remote/capture/observer.jsonl',
    'remote/capture/run.log', 'remote/capture/RERUN_RUNTIME.log',
    'remote/capture/est_poses_full.txt', 'remote/capture/attempt.json',
    'logs/run_supervisor.exit.txt', 'logs/offline_evaluation.exit.txt',
} | SPECIAL


def require(ok, error):
    if not ok:
        raise ValueError(error)


def digest(stream):
    h = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        h.update(chunk)
        size += len(chunk)
    return {'bytes': size, 'sha256': h.hexdigest()}


def hash_file(path):
    with path.open('rb') as stream:
        return digest(stream)


def read_json(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


def entries():
    paths = [ROOT / name for name in (ENTRANCE, 'TASK003_FINAL_REVIEW.md', 'EXECUTION_LOG.md')]
    paths.extend(p for p in ROOT.glob('TASK003_*') if p.is_file() and p.suffix in {'.csv', '.json'})
    for directory in FOLDERS:
        paths.extend(p for p in (ROOT / directory).rglob('*') if p.is_file() and
                     (p.suffix in SUFFIXES or p.relative_to(ROOT).as_posix() in SPECIAL))
    manifest_entries = {}
    for path in sorted(paths):
        name = path.relative_to(ROOT).as_posix()
        require(path.resolve() == path, f'Redirected evidence path: {name}')
        manifest_entries[name] = hash_file(path)
    require(ESSENTIAL <= manifest_entries.keys(), f'Missing evidence: {ESSENTIAL - manifest_entries.keys()}')
    return manifest_entries


def verify_records(files):
    receipt = read_json('remote/capture/LAUNCH_RECEIPT.json')
    attempt = read_json('remote/capture/attempt.json')
    preflight = read_json('evidence/TASK003_FINAL_PREFLIGHT.json')
    diff = read_json('evidence/CONFIG_EFFECTIVE_DIFF.json')
    browser = read_json('evidence/RERUN_BROWSER_FINAL_TRANSPORT.json')
    require(receipt['model_process_started'] and receipt['attempts_consumed'] == 1, 'Launch receipt')
    require(attempt['attempts_consumed'] == attempt['attempts_authorized'] == 1 and
            attempt['exit_code'] == 0 and attempt['retried'] is False, 'Attempt terminal status')
    model = attempt['model']
    require(model['input_frames'] == model['read_frames'] == model['valid_poses'] ==
            model['poses_exported'] == model['filler_frames'] == 487, 'Pose coverage')
    require(preflight['status'] == 'PASS_BEFORE_MODEL' and preflight['browser']['visible_synthetic_entities'] and
            browser['tracking_screenshot_visually_verified'], 'Browser admission and real render evidence')
    expected = {
        'remote/capture/trajectory.npz': model['trajectory_sha256'],
        'remote/capture/est_poses_full.txt': model['upstream_text_sha256'],
        'remote/capture/observer.jsonl': attempt['trace_sha256'],
        'remote/incoming/INPUT.json': preflight['manifest']['sha256'],
        'remote/incoming/native_config.yaml': preflight['sealed_config']['sha256'],
        'remote/capture/native_config.yaml': diff['actual_sha256'],
        'evidence/RERUN_BROWSER_SMOKE.png': preflight['browser']['screenshot_sha256'],
        'evidence/RERUN_BROWSER_TRACKING.png': browser['tracking_screenshot_sha256'],
        'evidence/RERUN_BROWSER_FINAL.png': browser['final_screenshot_sha256'],
    }
    for name, sha in expected.items():
        require(files[name]['sha256'] == sha, f'Run-time SHA-256 mismatch: {name}')
    require(files['remote/capture/observer.jsonl']['bytes'] == attempt['trace_bytes'], 'Trace size')
    for name in files:
        if name.endswith('.exit.txt'):
            require((ROOT / name).read_text(encoding='utf-8-sig').strip() == '0', f'Nonzero exit: {name}')
    return len(expected)


def verify_archive(path, manifest, manifest_raw):
    files = manifest['files']
    with ZipFile(path) as archive:
        members = archive.namelist()
        require(len(members) == len(set(members)) == len(files) + 1, 'Invalid member count')
        require(set(members) == set(files) | {MANIFEST.name}, 'Member set mismatch')
        bad = archive.testzip()
        require(bad is None, f'CRC failed: {bad}')
        require(archive.read(MANIFEST.name) == manifest_raw, 'Manifest content mismatch')
        for name, expected in files.items():
            with archive.open(name) as stream:
                require(digest(stream) == expected, f'SHA-256 or size mismatch: {name}')


def package(manifest, raw):
    require(not ARCHIVE.exists() and not MANIFEST.exists(), 'Refusing to overwrite a delivered archive')
    fd, tmp = tempfile.mkstemp(prefix='.task003_review_', suffix='.tmp', dir=ROOT)
    os.close(fd)
    temporary = Path(tmp)
    try:
        with ZipFile(temporary, 'w', ZIP_DEFLATED, compresslevel=6) as out:
            for name in manifest['files']:
                out.write(ROOT / name, name)
            out.writestr(MANIFEST.name, raw)
        verify_archive(temporary, manifest, raw)
        with MANIFEST.open('xb') as stream:
            stream.write(raw)
        temporary.rename(ARCHIVE)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--verify-only', action='store_true')
    args = cli.parse_args()
    files = entries()
    runtime_sha_sources = verify_records(files)
    if args.verify_only:
        raw = MANIFEST.read_bytes()
        manifest = json.loads(raw)
        require(manifest['files'] == files, 'Workspace evidence differs from manifest')
        verify_archive(ARCHIVE, manifest, raw)
    else:
        manifest = {'schema': 'GAMECAM_TASK003_FILE_SHA256_V1', 'count': len(files),
                    'excluded_from_self_hashing': [MANIFEST.name, ARCHIVE.name], 'files': files}
        raw = (json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')
        package(manifest, raw)
    print(json.dumps({'archive': str(ARCHIVE), **hash_file(ARCHIVE), 'zip_crc': 'PASS',
                      'payload_sha256_pass': len(files), 'zip_members': len(files) + 1,
                      'runtime_identity_crosschecks': runtime_sha_sources}, indent=2))


if __name__ == '__main__':
    main()
