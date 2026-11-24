"""Collect pinned evidence and verify the Task 002B document bundle."""

import hashlib
import json
from pathlib import PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

from audit_common import (AUDIT1, EVAL_SHA, FROZEN_NAME, LOCK_NAME, OUT, R1, R2,
                          SOURCES, ZIP, ZIP_SHA, cpu_guard, digest, load_contract, read_csv,
                          read_json, require, save_json, sha)

cpu_guard()

REQUIRED = (
    'TASK002B_DATA_AVAILABILITY_AND_HASH_AUDIT.md', 'INPUT_PREPROCESSING_PARITY_REPORT.md',
    'INPUT_PREPROCESSING_STAGE_TABLE.csv', 'R2_RPE_PER_SEGMENT.csv', 'R2_RPE_PER_SEQUENCE.csv',
    'R2_RPE_ENVIRONMENT_SUMMARY.csv', 'R2_SEQUENCE_BOOTSTRAP_COMPARISON.csv',
    'R2_TRANSLATION_RPE_REPORT.md', 'R2_ROTATION_RPE_REPORT.md', 'R2_ENVIRONMENT_MOTION_MAP.md',
    'TASK002B_FINAL_REVIEW.md',
)
EVIDENCE = (
    'README_请先读.md', 'SECURITY_AUDIT.json', 'EXECUTION_LOG.md', 'TASK002B_SOURCE_EXCERPTS.txt',
    'TASK002B_SOURCE_EVIDENCE_INDEX.json', 'TASK002B_FROZEN_EVIDENCE_AUDIT.json',
    'CPU_PIXEL_AUDIT.json', 'CPU_PREPROCESSING_REPLAY_SAMPLES.csv', 'RGB_SOURCE_SEGMENT_AUDIT.csv',
    'EXACT_JPEG_DUPLICATE_GROUPS.csv', 'R2_RUNTIME_INPUT_RECEIPT_PARITY.csv',
    'R2_CAMERA_K_PROVENANCE_AUDIT.json', 'R2_CAMERA_K_PROVENANCE_BY_SEQUENCE.csv',
    'R2_CAMERA_K_PROVENANCE_BY_SEGMENT.csv', 'R2_TRAJECTORY_AND_GT_INTEGRITY.csv',
    'R2_STATISTICAL_CONTRACT.json', 'R2_ATE_RPE_AGREEMENT.csv', 'R2_LOCAL_TRANSLATION_COMPRESSION_SCREEN.csv',
    'R2_COMPRESSION_BY_ENVIRONMENT.csv', 'R2_VAL007_RPE_BY_SCOPE.csv', 'R2_VAL007_LOCAL_INTERVAL_VERIFICATION.csv',
)
SPANS = (
    ('R1', 'pipeline/audit_viper.py', ((21, 27), (33, 66), (181, 197))),
    ('R1', 'pipeline/plan_segments.py', ((16, 42), (54, 82))),
    ('R1', 'pipeline/segment_input.py', ((11, 37), (59, 79))),
    ('R1', 'pipeline/run_segment.py', ((81, 149), (183, 207), (214, 224))),
    ('R2', 'pipeline/verify_pixels.py', ((36, 96), (121, 136))),
    ('R2', 'pipeline/run_original.py', ((36, 69), (88, 139))),
    ('R2', 'pipeline/validate_smoke.py', ((12, 36),)),
    ('R2', 'pipeline/offline_evaluation.py', ((17, 105), (277, 297))),
    ('DROID-SLAM', 'droid_slam/motion_filter.py', ((36, 88),)),
    ('DROID-SLAM', 'droid_slam/trajectory_filler.py', ((34, 72),)),
    ('DROID-SLAM', 'droid_slam/droid_net.py', ((149, 164),)),
    ('DROID-SLAM', 'droid_slam/droid.py', ((71, 85),)),
    ('DROID-SLAM', 'droid_slam/depth_video.py', ((213, 225),)),
    ('DROID-W', 'src/utils/datasets.py', ((134, 168),)),
    ('DROID-W', 'src/motion_filter.py', ((33, 110),)),
    ('DROID-W', 'src/tracker.py', ((77, 100),)),
    ('DROID-W', 'src/trajectory_filler.py', ((28, 78), (100, 137))),
    ('DROID-W', 'src/modules/droid_net/droid_net.py', ((157, 160),)),
    ('DROID-W', 'src/depth_video.py', ((40, 45), (332, 371))),
)


def collect_sources(r1_zip, r2_zip):
    blobs = {(r['repository'], r['path']): r for r in read_csv(AUDIT1/'SOURCE_ENTRY_VERIFICATION.csv')}
    blocks, index = ['Task 002B: read-only source excerpts (line numbers from verified local originals).'], []
    for group, name, ranges in SPANS:
        if group in ('R1', 'R2'):
            root, package = (R1, r1_zip) if group == 'R1' else (R2, r2_zip)
            data = (root/name).read_bytes()
            require(data == package.read(name), f'local source differs from sealed {group}: {name}')
            verification = 'BYTE_MATCH_TO_ORIGINAL_REVIEW_ZIP'
        else:
            root = SOURCES/group
            data = (root/name).read_bytes()
            blob = blobs[(group, name)]
            header = f'blob {len(data)}\0'.encode('ascii')
            require(blob['check'] == 'ARCHIVE_AND_SNAPSHOT_BLOB_VERIFIED' and int(blob['bytes']) == len(data)
                    and hashlib.sha1(header + data).hexdigest() == blob['git_sha1'], f'Git blob identity {name}')
            verification = 'GIT_BLOB_MATCH_TO_TASK001_VERIFIED_SNAPSHOT'
        lines = data.decode('utf-8-sig').splitlines()
        index.append(dict(owner=group, relative_path=name, local_path=str(root/name), sha256=sha(data),
                          source_verification=verification, line_ranges=ranges))
        blocks.append(f'\n{group}/{name}  sha256={sha(data)}')
        for lo, hi in ranges:
            require(1 <= lo <= hi <= len(lines), f'out-of-range source excerpt: {name}:{lo}-{hi}')
            blocks.append(f'Lines {lo}-{hi}:')
            blocks.extend(f'{i:4} | {lines[i-1]}' for i in range(lo, hi+1))
    (OUT/'TASK002B_SOURCE_EXCERPTS.txt').write_text('\n'.join(blocks)+'\n', encoding='utf-8')
    save_json('TASK002B_SOURCE_EVIDENCE_INDEX.json', {'status': 'PASS', 'files_verified': len(index), 'files': index})
    return len(index)


def verify_outputs():
    for name in REQUIRED:
        require((OUT/name).stat().st_size > 0, f'empty required deliverable: {name}')
    expected_sizes = {
        'R2_RPE_PER_SEGMENT.csv': 2944, 'R2_RPE_PER_SEQUENCE.csv': 376,
        'R2_RPE_ENVIRONMENT_SUMMARY.csv': 192, 'R2_SEQUENCE_BOOTSTRAP_COMPARISON.csv': 64,
        'INPUT_PREPROCESSING_STAGE_TABLE.csv': 11, 'R2_TRAJECTORY_AND_GT_INTEGRITY.csv': 184,
        'R2_RUNTIME_INPUT_RECEIPT_PARITY.csv': 92, 'R2_CAMERA_K_PROVENANCE_BY_SEQUENCE.csv': 47,
    }
    for name, size in expected_sizes.items():
        rows = read_csv(OUT/name)
        require(len(rows) == size and all(None not in r and None not in r.values() for r in rows), f'CSV schema: {name}')
    for name in ('pixel_audit', 'motion_audit_final', 'summarize_motion', 'calibration_audit_final'):
        require((OUT/'analysis_only'/f'{name}.exit.txt').read_text(encoding='utf-8-sig').strip() == '0', f'failed run: {name}')
    for name in ('TASK002B_FROZEN_EVIDENCE_AUDIT.json', 'CPU_PIXEL_AUDIT.json', 'R2_CAMERA_K_PROVENANCE_AUDIT.json'):
        require(read_json(OUT/name)['status'] == 'PASS', f'audit not passed: {name}')
    return expected_sizes


def run():
    delivery = OUT/'CHAT_REVIEW_PACKAGE'
    dest = delivery/'GAMECAM_DROID_W_TASK002B_REVIEW.zip'
    require(not dest.exists(), 'refusing to overwrite a ZIP review package')
    sizes = verify_outputs()
    require(digest(ZIP) == ZIP_SHA, 'R2 changed since audit')
    upstream = R1/'DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1_REVIEW_PACKAGE.zip'
    with ZipFile(ZIP) as r2_zip, ZipFile(upstream) as r1_zip:
        lock, _ = load_contract(r2_zip)
        require(digest(upstream) == lock['r1_review_sha256'], 'R1 review ZIP SHA')
        require(r1_zip.read('evidence/camera_provenance.json') == (R1/'evidence/camera_provenance.json').read_bytes(),
                'R1 camera ledger no longer matches original archive')
        require(sha(r2_zip.read('pipeline/offline_evaluation.py')) == EVAL_SHA, 'evaluation source SHA')
        count = collect_sources(r1_zip, r2_zip)
    save_json('SECURITY_AUDIT.json', dict(scope='Task 002B local CPU audit and packaging only',
              gpu_requested=False, gpu_used=False, cuda_context_initialized=False, checkpoint_deserialized=False,
              model_constructed=False, model_forward_executed=False, model_training=False, slam_executed=False,
              ablations_executed=False, task003_started=False, ssh_connected=False, new_data_downloaded=False,
              historical_files_written=False, production_source_or_config_changed=False,
              dataset_or_gt_modified=False, model_weight_modified=False,
              original_r1_and_r2_zip_hash_rechecked=True, original_corpus_in_zip=False,
              source_excerpt_files_verified=count, required_csv_row_counts_verified=sizes))

    order = (REQUIRED[-1], REQUIRED[0], REQUIRED[1], REQUIRED[7], REQUIRED[8], REQUIRED[9])
    single = ('GameCam-VO Task 002B | 聊天版评审单文件\n'
              '评审范围：检查证据能支持哪些结论、哪些还需要独立验证。\n'
              '请核对三点：实际回执与 CPU 重建是否分开；序列级统计和两种 K 是否分开；'
              '症状复发是否被误写成因果。不要把本次离线审计当成启动后续实验的授权。\n\n')
    single += '\n\n'.join(f'===== {name} =====\n' + (OUT/name).read_text(encoding='utf-8-sig').strip() for name in order)
    single += '\n'
    text_name = 'GAMECAM_TASK002B_CHAT_REVIEW.txt'
    files = {name: (OUT/name).read_bytes() for name in REQUIRED + EVIDENCE}
    files[text_name] = single.encode('utf-8')
    for p in sorted((OUT/'analysis_only').iterdir()):
        if p.is_file() and p.suffix in ('.py', '.log', '.txt'):
            files[p.relative_to(OUT).as_posix()] = p.read_bytes()
    for name in (LOCK_NAME, FROZEN_NAME):
        files[f'evidence/{name}'] = (R2/name).read_bytes()
    for name, data in files.items():
        path = PurePosixPath(name)
        require(not path.is_absolute() and '..' not in path.parts and path.suffix in ('.md', '.csv', '.json', '.py', '.txt', '.log'),
                f'unsafe or unintended package member: {name}')
        data.decode('utf-8-sig')
    manifest_name = 'FILE_SHA256_MANIFEST.json'
    manifest = dict(algorithm='SHA-256', self_entry='excluded',
                    files=[dict(path=n, bytes=len(data), sha256=sha(data)) for n, data in sorted(files.items())])
    save_json(manifest_name, manifest)
    files[manifest_name] = (OUT/manifest_name).read_bytes()
    delivery.mkdir(exist_ok=True)
    with (delivery/text_name).open('xb') as f:
        f.write(files[text_name])
    with ZipFile(dest, mode='x', compression=ZIP_DEFLATED, compresslevel=6) as z:
        for name, data in sorted(files.items()):
            z.writestr(name, data)
    with ZipFile(dest) as z:
        require(z.testzip() is None and len(z.namelist()) == len(files) and set(z.namelist()) == set(files), 'ZIP CRC or inventory')
        rows = json.loads(z.read(manifest_name))['files']
        members = {r['path']: r for r in rows}
        require(len(members) == len(rows) == len(files)-1 and set(members) == set(files)-{manifest_name}, 'manifest coverage')
        for name, row in members.items():
            data = z.read(name)
            require(len(data) == row['bytes'] and sha(data) == row['sha256'], f'ZIP internal SHA: {name}')
        require(all(n in members for n in REQUIRED), 'missing requested deliverable')
    report = dict(status='PASS', zip=dest.name, zip_bytes=dest.stat().st_size, zip_sha256=digest(dest),
                  zip_members=len(files), crc_pass=len(files), internal_sha256_match=len(rows),
                  required_deliverables_verified=len(REQUIRED), source_excerpt_files_verified=count,
                  standalone_text=text_name, standalone_text_bytes=(delivery/text_name).stat().st_size,
                  standalone_text_sha256=digest(delivery/text_name))
    (delivery/'ZIP_VERIFICATION.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (delivery/(dest.name+'.sha256')).write_text(f'{report["zip_sha256"]}  {dest.name}\n', encoding='ascii')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
