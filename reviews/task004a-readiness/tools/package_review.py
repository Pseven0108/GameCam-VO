"""Seal the small Task004-A review archive from an explicit file inventory."""
import csv
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from archive import file_entry, verify_zip
from contracts import ORDER, ROOT, need, new_json, read_json, stat_sha, stream_sha, strict_json, verify_matrix

MANIFEST = 'FILE_SHA256_MANIFEST.json'
ZIP_NAME = 'GAMECAM_TASK004A_RELEASE_READINESS_REVIEW.zip'
ZIP_RECEIPT = 'TASK004A_ZIP_VALIDATION.json'
RECHECK = 'evidence/MOCK_ARCHIVES_RECHECK.json'
TABLES = (
    'TASK004_ENDPOINT_RETENTION.csv',
    'TASK004_FIXED_RGB_ENDPOINT_METRICS.csv',
    'TASK004_DIRECT_KEYFRAME_ENDPOINT_METRICS.csv',
)
REPORTS = (
    'README_\u8bf7\u5148\u8bfb.md', 'EXECUTION_LOG.md', 'SECURITY_AUDIT.json',
    'TASK004A_RELEASE_READINESS.md', 'TASK004_ENDPOINT_RETENTION_PLAN.md',
    'TASK004_E5_F0_FINAL_RECHECK.md', 'TASK004A_RUNNER_AUDIT.md',
    'TASK004A_LOG_PARSER_TEST.md', 'TASK004A_RERUN_PREFLIGHT_PLAN.md',
    'TASK004A_STORAGE_ARCHIVE_PLAN.md', 'TASK004A_FINAL_REVIEW.md',
    'evidence/TASK004_INPUT_ARCHIVE_VERIFICATION.json', 'evidence/FROZEN_SOURCE_AND_HISTORY_RECHECK.json',
    'evidence/TASK003_HISTORICAL_REPLAY.json', 'evidence/F0_CONTROL_FLOW_CPU_MOCK.json', RECHECK,
)
PROBE_FILES = (
    'RERUN_LOCAL_PROBE_RESULT.json', 'browser_before.png', 'browser_after.png', 'browser_transport.json',
    'browser.stdout.txt', 'browser.stderr.txt', 'emitter.stdout.txt', 'emitter.stderr.txt',
    'rerun.stdout.txt', 'rerun.stderr.txt',
)
ATTEMPT_FILES = (
    'LAUNCH_INTENT.json', 'LAUNCH_RECEIPT.json', 'PROCESS_RECEIPT.json', 'VALIDATION_RECEIPT.json',
    'process.stdout.txt', 'process.stderr.txt', 'task004_policy_receipt.json',
)


def pending_tables(root):
    for name in TABLES:
        with (root/name).open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        need(tuple(r['arm'] for r in rows) == ORDER, 'pending table order mismatch')
        need(all(r['status'] == 'NOT_RUN' and not r['attempt_id'] and not r.get('displacement_ratio_pct')
                 and not r.get('rgb312_retained_kf') for r in rows), 'formal table contains unapproved measurements')


def mock_archive_evidence(root):
    campaign = root/'evaluation/mock_campaign_03'
    receiving = root/'evaluation/mock_receiver_03'
    result = read_json(campaign/'CAMPAIGN_RESULT.json')
    need(result['mode'] == 'CPU_MOCK_ONLY' and tuple(result['completed']) == tuple(result['started']) == ORDER
         and result['gpu_runs'] == 0 and not result['retried'], 'unexpected final mock campaign')
    files = [campaign/n for n in ('CAMPAIGN_CLAIM.json', 'CAMPAIGN_RESULT.json', 'SYNTHETIC_ENDPOINT_RETENTION.csv',
                                   'SYNTHETIC_FIXED_RGB_ENDPOINT_METRICS.csv', 'SYNTHETIC_DIRECT_KEYFRAME_ENDPOINT_METRICS.csv')]
    evidence = []
    for slot, arm in enumerate(ORDER, 1):
        matches = list(receiving.glob(f'{slot:02d}-{arm}-*.verified.json'))
        need(len(matches) == 1, f'{arm}: wrong receiving receipt count')
        receipt = matches[0]
        attempt = receipt.name.removesuffix('.verified.json')
        expected = read_json(receipt)
        source = verify_zip(campaign/'archives'/f'{attempt}.zip', expected_sha=expected['source']['sha256'],
                            expected_attempt=attempt)
        received = verify_zip(receiving/f'{attempt}.zip', expected_sha=source['sha256'], expected_attempt=attempt)
        need(expected['status'] == 'VERIFIED_COPY' and expected['cleanup_authorized'] is False
             and source == expected['source'] and received == expected['received'], f'{arm}: archive receipt disagreement')
        evidence.append(dict(arm=arm, attempt_id=attempt, bytes=source['bytes'], sha256=source['sha256'],
                             payload_matches=source['payload_matches'], source_crc=source['crc'],
                             received_crc=received['crc'], matching_zip_sha256=True))
        files.append(receipt)
        for name in ATTEMPT_FILES:
            path = campaign/attempt/name
            need(file_entry(path) == source['files'][name], f'{arm}: selected receipt changed after sealing')
            files.append(path)
    new_json(root/RECHECK, dict(status='PASS', scope='CPU_MOCK_ONLY', order=list(ORDER), checked=evidence))
    safety = root/'evaluation/safety_tests_02'
    files.extend(sorted(safety.glob('*_run/CAMPAIGN_RESULT.json')))
    return files


def verify_review(path):
    with ZipFile(path) as z:
        names = z.namelist()
        need(len(names) == len({name.casefold() for name in names}) and z.testzip() is None,
             'ZIP duplicate member or CRC failure')
        manifest = strict_json(z.read(MANIFEST))
        files = manifest['files']
        need(set(names) == set(files) | {MANIFEST} and len(files) == manifest['payload_member_count'],
             'review manifest coverage mismatch')
        for name, pin in files.items():
            need(z.getinfo(name).file_size == pin['bytes'], f'ZIP size mismatch: {name}')
            with z.open(name, 'r') as member:
                need(stream_sha(member) == pin['sha256'], f'ZIP SHA-256 mismatch: {name}')
    return dict(status='PASS', zip=str(path.resolve()), bytes=path.stat().st_size, zip_sha256=stat_sha(path),
                zip_crc='PASS', members=len(names), sha256_verified_payload_files=len(files))


def main(root):
    need(all(not (root/x).exists() for x in (ZIP_NAME, MANIFEST, ZIP_RECEIPT, RECHECK)),
         'review outputs already exist; refusing to overwrite')
    pending_tables(root)
    verify_matrix(root/'assets')
    for run in ('historical_replay', 'mock_campaign_03', 'release_tests_02', 'rerun_probe_05'):
        need((root/f'logs/{run}.exit.txt').read_text().strip() == '0', f'{run}: unexpected exit')
    tests = (root/'logs/release_tests_02.stderr.txt').read_text(encoding='utf-8')
    need(tests.count(' ... ok\n') == 14 and 'Ran 14 tests' in tests and tests.strip().endswith('OK'),
         'CPU test log does not confirm 14 passes')
    probe = root/'_local_probe/probe_05'
    p = read_json(probe/'RERUN_LOCAL_PROBE_RESULT.json')
    need(p['status'] == 'LOCAL_REAL_BROWSER_RENDER_PASS' and p['data'] == 'SYNTHETIC_ONLY'
         and not p['remote'] and not p['verified_model'] and p['browser_transport']['websocket_frames'] == 21
         and all(stat_sha(probe/f'browser_{x}.png') == p[f'{x}_sha256'] for x in ('before', 'after')),
         'Rerun diagnostic evidence mismatch')

    selected = mock_archive_evidence(root)
    selected.extend(root/n for n in (*REPORTS, *TABLES))
    selected.extend(probe/n for n in PROBE_FILES)
    groups = dict(assets={'.csv', '.json', '.py', '.diff', '.yaml'}, tools={'.py', '.mjs'},
                  tests={'.py'}, fixtures={'.py'}, logs={'.txt'})
    for group, extensions in groups.items():
        selected.extend(p for p in (root/group).rglob('*') if p.is_file() and p.suffix in extensions)
    payload = {}
    for path in sorted(selected):
        name = path.relative_to(root).as_posix()
        need(name not in payload and path.resolve(strict=True).is_relative_to(root) and path.is_file()
             and not path.is_symlink() and not getattr(path.lstat(), 'st_file_attributes', 0) & 0x400,
             f'invalid or duplicate review member: {name}')
        payload[name] = file_entry(path)
    doc = dict(schema='GAMECAM_TASK004A_REVIEW_MANIFEST_V1', algorithm='SHA-256',
               scope='Every archived payload member except this manifest', payload_member_count=len(payload), files=payload)
    manifest_text = json.dumps(doc, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    output = root/ZIP_NAME
    with ZipFile(output, 'x', compression=ZIP_DEFLATED, compresslevel=8) as z:
        for name in payload:
            z.write(root/name, arcname=name)
        z.writestr(MANIFEST, manifest_text)
    receipt = verify_review(output)
    new_json(root/MANIFEST, doc)
    new_json(root/ZIP_RECEIPT, receipt)
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main(ROOT)
