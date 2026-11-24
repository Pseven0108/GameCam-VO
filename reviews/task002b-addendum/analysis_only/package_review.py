"""Create reviewer bundles from an explicit set of already verified outputs."""
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
CHAT = ROOT / 'CHAT_REVIEW_PACKAGE'
NAME = 'GAMECAM_DROID_W_TASK002B_ADDENDUM'
MANIFEST = 'FILE_SHA256_MANIFEST.json'
REPORTS = [
    'README_请先读.md', 'TASK002B_ADDENDUM_FINAL_REVIEW.md',
    'VAL007_KEYFRAME_FILLER_ANALYSIS.md', 'FIVE_ENVIRONMENT_KEYFRAME_FILLER_REPORT.md',
    'TRAJECTORY_FILLER_SOURCE_DIFF.md', 'TASK003_RECOMMENDATION.md',
    'FIGURE_GUIDE.md', 'METRIC_TRACEABILITY.md', 'EXECUTION_LOG.md', 'SECURITY_AUDIT.json',
]
FIGURES = [
    'figures/VAL007_KEYFRAME_COMPRESSION.png',
    'figures/ENVIRONMENT_MATCHED_POSE.png', 'figures/ENVIRONMENT_MATCHED_RPE60.png',
]
LIGHT_TABLES = [
    'KEYFRAME_ID_AUDIT.csv', 'KEYFRAME_MEMBERSHIP_BY_ENVIRONMENT.csv',
    'VAL007_CASE_INTERVALS.csv', 'VAL007_ANCHOR_INTERVALS.csv', 'VAL007_SAME_TYPE_COMPARATORS.csv',
    'POSE_ERROR_ENVIRONMENT_PAIRED.csv', 'RPE_ENDPOINT_ENVIRONMENT_PAIRED.csv',
    'COMPRESSION_RECURRENCE_BY_ENVIRONMENT.csv', 'MATCHED_KEYFRAME_ANCHOR_SENSITIVITY.csv',
]
FULL_TABLES = [
    'FRAME_TYPE_MANIFEST.csv', 'KEYFRAME_POSE_ERROR.csv', 'FILLED_FRAME_POSE_ERROR.csv',
    'KEYFRAME_CONSECUTIVE_RPE.csv', 'RPE_BY_ENDPOINT_TYPE.csv', 'RPE_PAIR_DETAIL.csv', 'RPE_PAIR_SEGMENT_INDEX.csv',
    'DIRECT_FINAL_BA_ANCHOR_COMPARISON.csv', 'RPE_PARTITION_RECONCILIATION.csv',
    'POSE_ERROR_BY_SEGMENT_AND_TIME.csv', 'POSE_ERROR_BY_SEQUENCE.csv', 'POSE_FILL_VS_KEYFRAME_BY_TIME.csv',
    'RPE_ENDPOINT_TYPE_BY_SEQUENCE.csv', 'RPE_OWN_FILL_VS_KEYFRAME.csv', 'RPE_TIME_MOTION_STRATA.csv',
    'RPE_STANDARDIZED_BY_SEQUENCE.csv', 'RPE_STANDARDIZED_FILL_VS_KEYFRAME.csv',
    'MATCHED_KEYFRAME_ANCHOR_PAIR_DETAIL.csv', 'MATCHED_KEYFRAME_ANCHOR_SENSITIVITY_BY_SEGMENT.csv',
    'COMPRESSION_RUNS_SAME_ENDPOINT_CLASS.csv', 'COMPRESSION_SCREEN_BY_CLASS.csv', 'COMPRESSION_SCREEN_PAIRS.csv',
    'VAL007_FRAME_SERIES.csv', 'VAL007_SAME_OFFSET_PAIRS.csv',
]
EVIDENCE = [
    'evidence/AGGREGATE_SUMMARY.json', 'evidence/NUMERICAL_VERIFICATION.json',
    'evidence/SOURCE_AND_ANCHOR_VERIFICATION.json', 'evidence/SOURCE_PROVENANCE.csv',
    'evidence/FILLER_SOURCE_EXCERPTS.txt',
]
FULL_EVIDENCE = ['evidence/ORIGINAL_EVIDENCE_PRESERVATION.csv', 'evidence/R2_STAGE_AND_ALIGNMENT_INDEX.csv']
PROGS = ['decompose', 'aggregate', 'verify_sources_and_anchors', 'render_figures', 'verify_delivery_evidence']
LOGS = [f'logs/{s}.{ext}' for s in PROGS for ext in ('stdout.log', 'stderr.log', 'exit.txt')]
SCRIPTS = [f'analysis_only/{s}.py' for s in PROGS + ['case_data', 'metrics', 'package_review']]
KEY_SIGNS = re.compile(rb'(?:-----BEGIN (?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----|'
                       rb'[?&](?:token|password|secret)=[A-Za-z0-9._-]{12,}|'
                       rb'Authorization:\s*Bearer\s+[A-Za-z0-9_-]{18,}|'
                       rb'\b(?:hf_[A-Za-z0-9]{25,}|gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9_-]{30,})\b)', re.I)


def json_bytes(payload):
    return (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def sha_file(p):
    with p.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def scorecard(name, files, artifact):
    return {'archive': artifact.name, 'scope': name, 'algorithm': 'SHA-256',
            'manifest_excludes': [MANIFEST], 'files': [files[p] for p in files]}


def build_archive(archive, names, records, scope, bundle_readme=None):
    assert len(names) == len(set(names)), names
    files = {n: records[n] for n in names}
    if bundle_readme:
        name, data = bundle_readme
        files[name] = {'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    payload = scorecard(scope, files, archive)
    manifest = json_bytes(payload)
    with ZipFile(archive, 'x', compression=ZIP_DEFLATED, compresslevel=6, allowZip64=False) as out:
        for p in names:
            out.write(ROOT / p, p)
        if bundle_readme:
            out.writestr(*bundle_readme)
        out.writestr(MANIFEST, manifest)
    with ZipFile(archive, 'r') as inp:
        listing = inp.namelist()
        assert len(listing) == len(set(listing)) and set(listing) == {*files, MANIFEST}
        assert inp.testzip() is None, f'CRC failed for {archive.name}'
        assert inp.read(MANIFEST) == manifest
        for n, rec in files.items():
            assert inp.getinfo(n).file_size == rec['bytes'], n
            with inp.open(n) as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == rec['sha256'], n
    return {'path': str(archive), 'bytes': archive.stat().st_size, 'sha256': sha_file(archive),
            'zip_crc': 'PASS', 'zip_members': len(files)+1, 'member_sha256_verified': len(files),
            'manifest_excludes_self': True}, manifest


def main():
    assert not CHAT.exists(), CHAT
    full = ROOT / f'{NAME}_REVIEW.zip'
    light = CHAT / f'{NAME}_CHAT_LIGHT.zip'
    text = CHAT / f'{NAME}_CHAT_REVIEW.txt'
    external_check = ROOT / 'evidence/DELIVERY_VERIFICATION.json'
    assert not full.exists() and not external_check.exists() and not (ROOT / MANIFEST).exists()
    assert (ROOT/'logs/verify_delivery_evidence.exit.txt').read_text(encoding='ascii').strip() == '0'
    assert json.loads((ROOT/'logs/verify_delivery_evidence.stdout.log').read_text(encoding='utf-8-sig'))['status'] == 'PASS'
    lightweight = REPORTS + LIGHT_TABLES + FIGURES + EVIDENCE
    complete = lightweight + FULL_TABLES + FULL_EVIDENCE + LOGS + SCRIPTS
    records = {}
    for name in complete:
        p = ROOT / name
        assert p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(ROOT), p
        # The packaging script contains its own search signatures; other text is scanned as evidence.
        if p.suffix != '.png' and name != 'analysis_only/package_review.py':
            assert not KEY_SIGNS.search(p.read_bytes()), f'Possible access material in {name}'
        records[name] = {'path': name, 'bytes': p.stat().st_size, 'sha256': sha_file(p)}
    assert len(records) == len(complete)
    chat_intro = (
        'GameCam-VO Task 002B-Addendum | 中文独立评审材料\n'
        '这是本轮 CPU 离线评审的正文，包含案例数值、方法、五环境结果、源码差异和 Task 003 建议。\n'
        '审查重点：证据能否支持“压缩已在最终 BA 锚点”，还缺什么才能判定首次异常阶段及补位的增量。\n'
        '请区分直接观察、统计关联、源码行为和未经验证的机制；不批准或执行后续实验。\n'
    )
    parts = [chat_intro]
    for name in REPORTS[1:6]:
        parts.append(f'\n========== {name} ==========\n\n' + (ROOT/name).read_text(encoding='utf-8-sig').strip() + '\n')
    parts.append('\n图表另附：figures/VAL007_KEYFRAME_COMPRESSION.png、ENVIRONMENT_MATCHED_POSE.png、ENVIRONMENT_MATCHED_RPE60.png。\n')
    joined = ''.join(parts)
    assert not KEY_SIGNS.search(joined.encode('utf-8'))
    assert '0.02615' in joined and 'INSUFFICIENT' not in joined.splitlines()[0]
    CHAT.mkdir(exist_ok=False)
    with text.open('x', encoding='utf-8-sig', newline='\r\n') as f:
        f.write(joined)
    assert text.read_text(encoding='utf-8-sig') == joined
    light_readme = (
        '本 ZIP 只含轻量评审材料。逐帧、逐对大表和原始执行日志在完整版；不在本 ZIP。\n'
        '如不能解压，直接上传同目录的 CHAT_REVIEW.txt（完整文件名见交付记录）和关键图。\n'
    ).encode('utf-8')
    f, fm = build_archive(full, complete, records, 'FULL_DERIVED_EVIDENCE', None)
    l, _ = build_archive(light, lightweight, records, 'LIGHT_CHAT_REVIEW', ('LIGHT_PACKAGE_SCOPE.txt', light_readme))
    with (ROOT/MANIFEST).open('xb') as output:
        output.write(fm)
    standalone = {'path': str(text), 'bytes': text.stat().st_size, 'encoding': 'UTF-8 with BOM', 'sha256': sha_file(text)}
    result = {'status': 'PASS', 'full': f, 'light': l, 'standalone_text': standalone,
              'contains_original_rgb': False, 'contains_model_weights': False, 'contains_full_source_repositories': False,
              'note': 'ZIP SHA-256 is recorded outside both archives. Each archive manifest covers all members except itself.'}
    with external_check.open('xb') as output:
        output.write(json_bytes(result))
    for p, obj in ((full, f), (light, l), (text, standalone)):
        with (p.with_suffix(p.suffix + '.sha256')).open('x', encoding='ascii', newline='\n') as out:
            out.write(f"{obj['sha256']}  {p.name}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
