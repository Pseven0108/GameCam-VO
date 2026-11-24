"""Verify the static Task 004 review and build a small ZIP; no remote or model access."""

import csv
from datetime import datetime, timezone
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TASK003 = ROOT.parent / 'DROID_W_TASK003_VAL007_OBSERVATION_R1'
ZIP = ROOT / 'GAMECAM_TASK004_CAUSAL_ABLATION_REVIEW.zip'
MANIFEST = ROOT / 'FILE_SHA256_MANIFEST.json'
RECEIPT = ROOT / 'ZIP_VALIDATION.json'
ESSENTIAL = ('README_请先读.md', 'TASK004_RESEARCH_DESIGN.md', 'TASK004_FACTORIAL_MATRIX.csv',
             'TASK004_FACTOR_INTERACTION_PLAN.md', 'TASK004_LOW_LEVEL_SWITCH_AUDIT.md',
             'TASK004_PHASE_SCOPE_AUDIT.md', 'TASK004_E0_E8_CONFIG_DIFFS.md',
             'TASK004_INSTRUMENTATION_PLAN.md', 'TASK004_METRIC_AND_STATISTICS_PLAN.md',
             'TASK004_E5_FINAL_BA_PLAN.md', 'TASK004_RESOURCE_AND_RUN_BUDGET.md',
             'TASK004_FINAL_REVIEW.md', 'EXECUTION_LOG.md', 'SECURITY_AUDIT.json')
SELECTED = ('TASK003_FINAL_REVIEW.md', 'TASK003_ACTIVE_MECHANISMS_BY_STAGE.csv',
            'TASK003_312_328_LOCAL_BA_TIMELINE.csv', 'TASK003_VAL007_INTERVAL_ANALYSIS.csv',
            'TASK003_EXPORTED_RPE_OFFSETS.csv', 'TASK003_TRACE_PROCESSING.json',
            'remote/capture/attempt.json', 'remote/capture/resource_samples.csv',
            'evidence/CONFIG_EFFECTIVE_DIFF.json', 'evidence/TASK003_TARGET_EVENT_CROSSCHECK.json')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def stamp(data):
    return dict(bytes=len(data), sha256=sha256(data).hexdigest())


def read_json(path):
    return json.loads(path.read_bytes())


def encoded(obj):
    return (json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def retain_bytes(path, data):
    if path.exists():
        require(path.read_bytes() == data, f'Different content at {path}')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as out:
            out.write(data)


def verify_file(path, recorded):
    with path.open('rb') as handle:
        digest = sha256()
        count = 0
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            count += len(block)
            digest.update(block)
    require(count == recorded['bytes'] and digest.hexdigest() == recorded['sha256'], f'Identity mismatch: {path}')
    return dict(path=str(path), bytes=count, sha256=digest.hexdigest())


def historical_recheck():
    history = read_json(ROOT / 'evidence/HISTORICAL_INPUTS.json')
    source = read_json(ROOT / 'evidence/SOURCE_AND_CANDIDATE_IDENTITY.json')
    verified = [verify_file(Path(row['path']), row) for row in history['historical_files'].values()]
    blobs = [verify_file(Path(row['path']), row) for row in source['verified_source_blobs'].values()]
    require(len(verified) == 21 and len(blobs) == 13, 'Unexpected original evidence coverage')
    archive = verify_file(Path(history['archive']['path']), history['archive'])
    r2 = ROOT.parent / 'DROID_W_TASK003_VAL007_RUNTIME_LOCALIZATION/evidence/sealed_r2'
    ref = r2 / 'wild_reference/val_007_full_00001-00487'
    protected = read_json(TASK003 / 'evidence/POSTRUN_ASSET_PRESERVATION.json')['historical_R2']
    originals = [verify_file(ref / Path(row['path']).name, row) for row in protected]
    verify_file(ROOT / 'candidates/r2_sealed_config.yaml', protected[0])
    verify_file(ROOT / 'candidates/task004_run_segment.py', source['patched_candidate_runner'])
    for path in sorted((ROOT / 'candidates/preview').rglob('*.py')):
        key = path.relative_to(ROOT / 'candidates/preview').as_posix()
        require(stamp(path.read_bytes())['sha256'] == source['task004_postimages'][key], f'Candidate preview mismatch: {key}')
    require(stamp((ROOT / 'candidates/task004_controls.py').read_bytes())['sha256'] ==
            source['task004_postimages']['task004_controls.py'], 'Policy implementation mismatch')
    for name in SELECTED:
        original = history['historical_files'][name]
        data = (TASK003 / name).read_bytes()
        require(stamp(data)['sha256'] == original['sha256'], f'Review evidence mismatch: {name}')
        retain_bytes(ROOT / 'evidence/task003_selected' / name, data)
    return dict(status='PASS', method='local byte checks only; no SSH, GPU, model weights or RGB access',
                historical_archive=archive, task003_reference_files=verified, frozen_source_files=blobs,
                sealed_r2_local_copies=originals, selected_historical_copies=list(SELECTED),
                original_task003_archive_crc_checked_during_candidate_build=history['crc_pass'])


def verify_matrix():
    with (ROOT / 'TASK004_FACTORIAL_MATRIX.csv').open(encoding='utf-8', newline='') as handle:
        rows = list(csv.DictReader(handle))
    expected = dict(E0=(1, 1, 1), E1=(0, 1, 1), E2=(1, 0, 1), E3=(1, 1, 0),
                    E4=(0, 0, 1), E6=(0, 1, 0), E7=(1, 0, 0), E8=(0, 0, 0))
    require(len(rows) == 8 and {r['arm'] for r in rows} == set(expected), 'Missing or repeated arm')
    require({tuple(int(r[k]) for k in 'DWU') for r in rows} == set(product((0, 1), repeat=3)), 'Incomplete cube')
    for row in rows:
        name = row['arm']
        key = f'policies/{name}.json'
        require(row['policy_file'] == key and row['seed'] == '43' and row['status'] == 'CPU_REVIEW_ONLY', name)
        data = (ROOT / key).read_bytes()
        policy = json.loads(data)
        require(stamp(data)['sha256'] == row['policy_sha256'] and
                tuple(int(row[k]) for k in 'DWU') == expected[name] == tuple(policy['local_dwu']) and
                policy['arm'] == name and policy['final_phases'] == 2, f'Matrix-policy mismatch: {name}')
    require([r['arm'] for r in sorted(rows, key=lambda r: int(r['screening_slot']))] ==
            ['E3', 'E4', 'E7', 'E0', 'E8', 'E6', 'E1', 'E2'], 'Policy order mismatch')
    return len(rows)


def main():
    for path in (ZIP, MANIFEST, RECEIPT):
        require(not path.exists(), f'Refusing to overwrite {path}')
    for activity in ('verify_frozen_sources', 'prepare_release', 'cpu_mock_release'):
        require((ROOT / 'logs' / f'{activity}.exit.txt').read_text().strip() == '0', f'Failed {activity}')
    report = (ROOT / 'logs/cpu_mock_release.stderr.txt').read_text(encoding='utf-8')
    require(report.count(' ... ok\n') == 16 and 'Ran 16 tests' in report and report.strip().endswith('OK'), 'Mock record incomplete')
    policy_count = verify_matrix()
    preservation = ROOT / 'evidence/HISTORICAL_PRESERVATION_RECHECK.json'
    original_evidence = historical_recheck()
    retain_bytes(preservation, encoded(original_evidence))
    paths = set(ESSENTIAL)
    for folder in ('candidates', 'policies', 'logs', 'tools'):
        paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / folder).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py', '.diff', '.txt', '.json', '.yaml'})
    paths.update(('evidence/HISTORICAL_INPUTS.json', 'evidence/SOURCE_AND_CANDIDATE_IDENTITY.json',
                  'evidence/HISTORICAL_PRESERVATION_RECHECK.json'))
    paths.update(f'evidence/task003_selected/{name}' for name in SELECTED)
    payload = {}
    for name in sorted(paths):
        path = ROOT / name
        require(path.resolve().is_relative_to(ROOT) and not path.is_symlink(), f'Unexpected path: {path}')
        require(path.stat().st_size < 1024 * 1024, f'Unexpectedly large review member: {name}')
        payload[name] = path.read_bytes()
    manifest_data = encoded(dict(algorithm='SHA-256', coverage='all archive members except this manifest',
                                 files={name: stamp(data) for name, data in payload.items()}))
    with zipfile.ZipFile(ZIP, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for name, data in payload.items():
            out.writestr(name, data)
        out.writestr(MANIFEST.name, manifest_data)
    with zipfile.ZipFile(ZIP) as z:
        members = z.namelist()
        require(z.testzip() is None and len(set(members)) == len(members), 'CRC or duplicate filename failure')
        require(set(members) == set(payload) | {MANIFEST.name} and z.read(MANIFEST.name) == manifest_data,
                'Archive membership or manifest mismatch')
        for name, expected in json.loads(z.read(MANIFEST.name))['files'].items():
            require(stamp(z.read(name)) == expected == stamp((ROOT / name).read_bytes()), f'ZIP SHA mismatch: {name}')
    retain_bytes(MANIFEST, manifest_data)
    receipt = dict(status='PASS', checked_utc=datetime.now(timezone.utc).isoformat(), path=str(ZIP),
                   zip_crc_pass=True, zip_members=len(members), payload_sha256_matches=len(payload),
                   manifest_sha256=stamp(manifest_data)['sha256'], matrix_policy_identity_matches=policy_count,
                   historical_reference_identity_matches=len(original_evidence['task003_reference_files']),
                   frozen_file_identity_matches=len(original_evidence['frozen_source_files']), mock_tests_passed=16,
                   build_and_verification_exit_code=0, **stamp(ZIP.read_bytes()))
    retain_bytes(RECEIPT, encoded(receipt))
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
