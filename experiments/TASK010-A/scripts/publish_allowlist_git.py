"""Bulk-transfer fallback when the GitHub connector's binary channel is unavailable.

Build an isolated index from the reviewed parent. Never stage the user's index,
switch branches, force-push, change repository visibility, or inspect credentials.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
PRIVATE = ROOT / 'experiments/TASK010-A/private/publication'


def git(*args, data=None, env=None):
    result = subprocess.run(['git', *args], cwd=ROOT, input=data,
                            capture_output=True, env=env)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace'))
    return result.stdout.decode('utf-8').strip()


def main():
    manifest = json.loads((PRIVATE / 'allowlist.json').read_text(encoding='utf-8'))
    index = PRIVATE / 'publication.index'
    if index.exists():
        raise FileExistsError('Use a fresh isolated index; do not overwrite an uncertain publication')
    env = os.environ.copy()
    env.update(GIT_INDEX_FILE=str(index), GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
    git('read-tree', manifest['parent_sha'], env=env)
    entries = []
    for record in manifest['entries']:
        source = Path(record['source'])
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != record['sha256']:
            raise ValueError('Publication content changed: ' + record['path'])
        identity = git('hash-object', '-w', '--no-filters', '--', str(source), env=env)
        if identity != record['git_blob_sha']:
            raise ValueError('Git blob identity mismatch: ' + record['path'])
        mode = '100755' if source.suffix == '.sh' else '100644'
        entries.append(f'{mode} {identity}\t{record["path"]}\0'.encode('utf-8'))
    git('update-index', '-z', '--index-info', data=b''.join(entries), env=env)
    tree = git('write-tree', env=env)
    commit = git('commit-tree', tree, '-p', manifest['parent_sha'], '-m',
                 'TASK010-A: evaluate dynamic, geometry and relative-depth prior prototypes', env=env)
    receipt = {'branch': manifest['branch'], 'commit': commit, 'tree': tree,
               'parent': manifest['parent_sha'], 'file_count': len(entries),
               'isolated_index': str(index), 'current_branch_unchanged': True,
               'visibility_change': False, 'force_push': False, 'push_status': 'NOT_ATTEMPTED'}
    path = PRIVATE / 'git_publication_receipt.json'
    path.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    result = subprocess.run(['git', '-c', 'credential.interactive=never', 'push', '--porcelain',
                             'https://github.com/Pseven0108/GameCam-VO.git',
                             f'{commit}:refs/heads/{manifest["branch"]}'], cwd=ROOT,
                            env=env, capture_output=True)
    log = (result.stdout + result.stderr).decode('utf-8', errors='replace')
    (PRIVATE / 'git_push.log').write_text(log, encoding='utf-8')
    receipt.update(push_status='COMPLETE' if result.returncode == 0 else 'FAILED', returncode=result.returncode)
    path.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))
    print(log)
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
