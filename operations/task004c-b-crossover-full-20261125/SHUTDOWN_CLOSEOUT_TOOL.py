"""Record actual console shutdown after two unsuccessful platform CLI invocations.

The sealed experiment ZIP is never changed. No SSH or model command is issued.
"""
import datetime
import hashlib
import json
import pathlib
import re
import urllib.request
from publish_completed_review_r3 import ROOT, REPO, SLUG, REL, BRANCH, git, sha


def load(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sanitize(text):
    text = re.sub(r'(?:hz\d+|sc\d+)-ssh\.gpuhome\.cc(?::\d+)?', '<REDACTED_SSH_ENDPOINT>', text)
    text = text.replace('<REDACTED_INSTANCE_ID>', '<REDACTED_INSTANCE_ID>')
    text = re.sub(r'SHA256:[A-Za-z0-9+/]{25,}={0,2}', '<REDACTED_SSH_FINGERPRINT>', text)
    return text


def main():
    publication = load('GITHUB_R3_PUBLICATION_RECEIPT.json')
    first = load('SHUTDOWN_EXECUTION_RECEIPT.json')
    second = load('SHUTDOWN_TERMINAL_REPAIR_RECEIPT.json')
    package = load('COMPLETED_PACKAGE_VALIDATION.json')
    assert publication['published'] and publication['anonymous_CRC'] == 'PASS'
    assert git('rev-parse', 'HEAD') == publication['commit']
    assert not git('status', '--porcelain'), 'Reconcile any earlier partial publication first'
    assert first['user_authorized'] and first['all_results_local_SHA_verified']
    assert any(p['marker_returned'] for p in first['read_only_probes'])
    assert any(p['marker_returned'] for p in second['read_only_probes'])
    assert first['new_GPU_experiments_started'] == second['new_GPU_experiments_started'] == 0

    screen = ROOT / 'evidence/R3_INSTANCE_STOPPED_CONSOLE.jpg'
    ax = ROOT / 'evidence/R3_INSTANCE_STOPPED_CONSOLE_AX.txt'
    text = ax.read_text(encoding='utf-8')
    assert screen.is_file() and screen.stat().st_size > 1000
    assert '<REDACTED_INSTANCE_ID>' in text and 'text 已停止' in text and 'RTX 3090 / 1卡' in text
    assert sha(package['ZIP_path']) == publication['ZIP_SHA256']

    local = {
        'user_authorized': True,
        'status': 'INSTANCE_STOPPED_CONFIRMED_IN_CLOUD_CONSOLE',
        'actual_shutdown_method': 'cloud_console_shutdown_switch_and_confirmation',
        'terminal_shutdown_success': False,
        'terminal_invocations': 2,
        'automatic_retry_loop': False,
        'terminal_exit_zero_did_not_prove_shutdown': True,
        'target': {'endpoint': '<REDACTED_SSH_ENDPOINT>', 'instance_id': '<REDACTED_INSTANCE_ID>', 'gpu_model': 'RTX 3090'},
        'endpoint_matched_to_console_before_action': True,
        'console_transition_observed': ['运行中', '关机中', '已停止'],
        'console_stopped_observed_utc': '2026-11-24T19:35:30.433Z',
        'instance_console_power_state_independently_verified': True,
        'billing_state_independently_verified': False,
        'instance_deleted_or_released': False,
        'historical_data_deleted': False,
        'new_GPU_experiments_started_for_shutdown': 0,
        'results_archived_before_shutdown': True,
        'sealed_review_ZIP_unchanged': True,
        'review_ZIP_SHA256': publication['ZIP_SHA256'],
        'console_screenshot_local_path': str(screen),
        'console_screenshot_sha256': sha(screen),
        'console_AX_local_path': str(ax),
        'console_AX_sha256': sha(ax),
        'terminal_receipt_sha256': sha(ROOT / 'SHUTDOWN_EXECUTION_RECEIPT.json'),
        'interactive_terminal_receipt_sha256': sha(ROOT / 'SHUTDOWN_TERMINAL_REPAIR_RECEIPT.json'),
        'receipt_created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    local_path = ROOT / 'SHUTDOWN_CONSOLE_VERIFIED_RECEIPT.json'
    assert not local_path.exists(), 'Do not overwrite an existing closeout receipt'
    write(local_path, local)

    attempts = []
    for method, receipt, error in [
        ('pinned_SSH_noninteractive_platform_shutdown', first, 'level=error (no explanatory message)'),
        ('pinned_SSH_interactive_login_shell_shutdown', second, 'ERRO[0000] (no explanatory message)'),
    ]:
        attempts.append({
            'method': method,
            'start_unix': receipt['start_unix'],
            'end_unix': receipt['end_unix'],
            'exit_code': receipt['ssh_exit_code'],
            'observed_error': error,
            'stdout_sha256': receipt['stdout_sha256'],
            'stderr_sha256': receipt['stderr_sha256'],
            'subsequent_read_only_SSH_probes': [
                {k: p[k] for k in ('unix', 'ssh_exit_code', 'marker_returned')}
                for p in receipt['read_only_probes']
            ],
            'shutdown_success': False,
        })
    public = {k: v for k, v in local.items() if k not in (
        'target', 'console_screenshot_local_path', 'console_AX_local_path')}
    public['target_identity_sha256'] = hashlib.sha256(local['target']['instance_id'].encode()).hexdigest()
    public['target_gpu_model'] = 'RTX 3090'
    public['SSH_host_key_was_pinned'] = True
    public['terminal_attempts'] = attempts
    public['console_screenshot_published'] = False
    public['screenshot_retained_locally_with_SHA256'] = True
    public['raw_access_metadata_published'] = False
    public['note'] = ('Both platform CLI attempts returned exit 0 but logged errors and left SSH reachable. '
                      'The authorized console fallback was matched to the experiment SSH endpoint before '
                      'shutdown; the console then visibly changed to stopping and stopped. '
                      'Billing status was not separately verified.')
    payload = json.dumps(public, ensure_ascii=False, indent=2) + '\n'
    assert not re.search(r'-----BEGIN.*PRIVATE KEY|(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}|[?&]token=[A-Za-z0-9_-]{10,}', payload)
    op = REPO / 'operations' / SLUG
    (op / 'INSTANCE_SHUTDOWN_RECEIPT.json').write_text(payload, encoding='utf-8')
    (op / 'SHUTDOWN_CLOSEOUT_TOOL.py').write_text(sanitize(pathlib.Path(__file__).read_text(encoding='utf-8')), encoding='utf-8')
    message = ('实验结果、本地完整C0备份及GitHub评审包核验后，已完成关机。'
               '平台终端shutdown两次调用均报错且SSH仍可达，最终使用已授权的云控制台关机，'
               '页面已实测显示“已停止”。没有宣称终端命令成功，计费状态未单独核验。')
    (op / 'README.md').write_text(
        '# Closeout operation receipts\n\n' + message +
        '\n\nThe immutable review ZIP remains sealed and unchanged. '
        'These supplementary receipts document actions after its seal. '
        'The complete C0 binary and the console screenshot remain in verified local storage; '
        'no additional C0, model run, dataset deletion, or instance release occurred.\n', encoding='utf-8')
    original = '用户已授权在归档发布核验后执行 shutdown；本提交封存时尚未执行，实际回执另行补充。'
    for name in ('PROJECT_STATUS.md', 'README.md'):
        path = REPO / name
        current = path.read_text(encoding='utf-8')
        assert original in current, name
        path.write_text(current.replace(original, message), encoding='utf-8')
    manifest = {'excludes_self': True, 'files': {}}
    for path in sorted(op.iterdir()):
        if path.is_file() and path.name != 'OPERATION_FILE_SHA256_MANIFEST.json':
            manifest['files'][path.name] = {'bytes': path.stat().st_size, 'sha256': sha(path)}
    write(op / 'OPERATION_FILE_SHA256_MANIFEST.json', manifest)
    git('add', '--', 'operations/' + SLUG, 'PROJECT_STATUS.md', 'README.md')
    git('commit', '-m', 'Record confirmed console shutdown after platform CLI errors')
    head = git('rev-parse', 'HEAD')
    git('push', 'origin', BRANCH, timeout=300)
    assert git('ls-remote', '--heads', 'origin', 'refs/heads/' + BRANCH).split()[0] == head
    for relative in ('operations/' + SLUG + '/INSTANCE_SHUTDOWN_RECEIPT.json',
                     'operations/' + SLUG + '/OPERATION_FILE_SHA256_MANIFEST.json',
                     'PROJECT_STATUS.md'):
        request = urllib.request.Request(
            'https://raw.githubusercontent.com/Pseven0108/GameCam-VO/' + head + '/' + relative,
            headers={'User-Agent': 'GameCam-VO-anonymous-closeout-verification'})
        with urllib.request.urlopen(request, timeout=60) as response:
            actual = response.read()
        assert actual == (REPO / relative).read_bytes(), relative
    assert sha(package['ZIP_path']) == publication['ZIP_SHA256']
    receipt = {
        'published': True,
        'initial_review_commit': publication['commit'],
        'final_closeout_commit': head,
        'sealed_review_ZIP_unchanged': True,
        'ZIP_URL': publication['ZIP_URL'],
        'ZIP_SHA256': publication['ZIP_SHA256'],
        'review_URL': 'https://github.com/Pseven0108/GameCam-VO/blob/' + head + '/' + REL + '/FINAL_REVIEW.md',
        'directory_URL': 'https://github.com/Pseven0108/GameCam-VO/tree/' + head + '/' + REL,
        'shutdown_receipt_URL': 'https://github.com/Pseven0108/GameCam-VO/blob/' + head + '/operations/' + SLUG + '/INSTANCE_SHUTDOWN_RECEIPT.json',
        'anonymous_final_receipt_readback': 'PASS',
        'shutdown_observed_status': local['status'],
        'instance_console_power_state_independently_verified': True,
        'billing_state_independently_verified': False,
    }
    write(ROOT / 'GITHUB_R3_SHUTDOWN_PUBLICATION_RECEIPT.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
