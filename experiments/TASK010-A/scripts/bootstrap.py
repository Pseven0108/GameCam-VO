"""Read-only historical intake and official source snapshots for TASK010-A."""
import concurrent.futures
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT / 'experiments/TASK010-A'
OLD = Path('D:/aaa/GameCam-VO-TASK009')
MAIN = Path('D:/aaa/GameCam-VO')
EXT = Path('D:/aaa/external_models/TASK010A')
REPOS = {'gmos': 'Jyxarthur/gmos', 'GeoMotion': 'zjutcvg/GeoMotion',
         'romo': 'google-deepmind/romo', 'DynOSeg': 'ACFR-RPG/DynOSeg',
         'DYNAPO': 'wuzy2115/DYNAPO', 'monst3r': 'junyi42/monst3r',
         'Pi3': 'yyfz233/Pi3', 'sam2': 'facebookresearch/sam2'}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(b)
    return h.hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'GameCam-VO-Research-Audit'})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()


def snapshot(item):
    name, repo = item
    record = {'name': name, 'repo': repo, 'retrieved_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    try:
        metadata = json.loads(get(f'https://api.github.com/repos/{repo}'))
        commit = json.loads(get(f'https://api.github.com/repos/{repo}/commits/{metadata["default_branch"]}'))
        record.update(commit=commit['sha'], default_branch=metadata['default_branch'],
                      license=(metadata.get('license') or {}).get('spdx_id'),
                      commit_date=commit['commit']['committer']['date'], official_url=metadata['html_url'])
        path = EXT / name
        if not path.exists():
            data = get(f'https://codeload.github.com/{repo}/zip/{commit["sha"]}')
            if len(data) > 300 * 1024**2:
                raise RuntimeError('Source snapshot exceeded bounded download')
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for member in z.infolist():
                    relative = Path(*Path(member.filename).parts[1:])
                    dest = path / relative
                    if not dest.resolve().is_relative_to(path.resolve()):
                        raise RuntimeError('Unsafe source path')
                    if not member.is_dir():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(z.read(member))
            record['archive_sha256'] = hashlib.sha256(data).hexdigest()
            dump(EXT / (name + '.source_identity.json'), record)
        else:
            old = json.loads((EXT / (name + '.source_identity.json')).read_text())
            if old['commit'] != record['commit']:
                raise RuntimeError('Existing source snapshot identity differs; do not overwrite')
            record = old
        record['source_files'] = sum(p.is_file() for p in path.rglob('*'))
        record['status'] = 'SOURCE_AVAILABLE'
    except Exception as e:
        record.update(status='SOURCE_FETCH_FAILED', error=str(e))
    print(json.dumps(record), flush=True)
    return record


def main():
    for sub in ['00_project_audit', '01_failure_diagnosis', '02_literature_and_code',
                '03_candidate_inference', '04_geometry_residual', '05_fusion_methods',
                '06_droidw_integration', '07_cross_scene_evaluation', '08_reports',
                '09_reproducibility', 'private', 'outputs', 'tests']:
        (TASK / sub).mkdir(parents=True, exist_ok=True)
    paths = []
    for base in [OLD / 'gamecam', OLD / 'external/DROID-W/src', OLD / 'experiments/TASK009/outputs']:
        paths += [p for p in base.rglob('*') if p.is_file() and
                  p.suffix in {'.py', '.json', '.jsonl', '.yaml', '.csv', '.npz'} and '__pycache__' not in p.parts]
    dump(TASK / 'private/HISTORICAL_PROTECTION_BEFORE.json',
         [{'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(paths)])
    for name in ['REPO_STATE', 'TASK009_REPO_STATE']:
        repo = ROOT if name == 'REPO_STATE' else OLD
        dump(TASK / ('00_project_audit/' + name + '.json'),
             {cmd: subprocess.check_output(['git', '-C', str(repo), *args], text=True)
              for cmd, args in [('head', ['rev-parse', 'HEAD']), ('branch', ['branch', '--show-current']),
                                ('status', ['status', '--short'])]})
    EXT.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(snapshot, REPOS.items()))
    dump(TASK / '02_literature_and_code/SOURCE_SNAPSHOTS.json', records)


if __name__ == '__main__':
    main()
