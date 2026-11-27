"""Verify the public fixed commit without credentials, then permit local ZIP cleanup."""
import csv
import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[3]
PRIVATE = ROOT / 'experiments/TASK010-A/private/publication'


def get(url):
    # No cookie, token, signed URL or authenticated credential is used.
    with urlopen(Request(url, headers={'User-Agent': 'GameCam-VO-Review-Verification'}), timeout=45) as response:
        return response.read()


def main():
    publication = json.loads((PRIVATE / 'git_publication_receipt.json').read_text(encoding='utf-8'))
    manifest = json.loads((PRIVATE / 'allowlist.json').read_text(encoding='utf-8'))
    expected = json.loads((ROOT / 'deliveries/TASK010A_PACKAGE_VERIFICATION.json').read_text(encoding='utf-8'))
    commit = publication['commit']
    raw = f'https://raw.githubusercontent.com/Pseven0108/GameCam-VO/{commit}/'
    meta = json.loads(get('https://api.github.com/repos/Pseven0108/GameCam-VO'))
    assert meta['private'] is False and meta['visibility'] == 'public'
    assert meta['default_branch'] == 'codex/research-review-20261124'
    print('Public visibility and default branch verified', flush=True)
    zip_data = get(raw + 'review_packages/GAMECAM_TASK010A_REVIEW.zip')
    actual = hashlib.sha256(zip_data).hexdigest()
    assert actual == expected['zip_sha256']
    external_sha = get(raw + 'review_packages/GAMECAM_TASK010A_REVIEW.zip.sha256').decode().split()[0]
    assert external_sha == actual
    with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
        assert z.testzip() is None
        records = list(csv.DictReader(io.StringIO(z.read('SHA256_MANIFEST.csv').decode('utf-8'))))
        for record in records:
            content = z.read(record['path'])
            assert len(content) == int(record['bytes'])
            assert hashlib.sha256(content).hexdigest() == record['sha256']
        assert len(records) == expected['internal_sha256_verified']
        remote_manifest = get(raw + 'reviews/task010a-dynamic-geometry-20261127/SHA256_MANIFEST.csv')
        assert remote_manifest == z.read('SHA256_MANIFEST.csv')
    print('Downloaded ZIP: SHA-256, CRC, all internal entries and expanded manifest verified', flush=True)
    tree = json.loads(get(f'https://api.github.com/repos/Pseven0108/GameCam-VO/git/trees/{publication["tree"]}?recursive=1'))
    assert tree['sha'] == publication['tree'] and not tree.get('truncated')
    blobs = {e['path']: e['sha'] for e in tree['tree'] if e['type'] == 'blob'}
    for entry in manifest['entries']:
        assert blobs[entry['path']] == entry['git_blob_sha'], entry['path']
    report = get(raw + 'reviews/task010a-dynamic-geometry-20261127/FINAL_REVIEW.md')
    assert report == (ROOT / 'reviews/task010a-dynamic-geometry-20261127/FINAL_REVIEW.md').read_bytes()
    result = {'status': 'PASS', 'commit': commit, 'tree': publication['tree'],
              'authentication_used': False, 'visibility': 'public', 'default_branch_unchanged': True,
              'published_blob_identities_verified': len(manifest['entries']), 'zip_sha256': actual,
              'zip_bytes': len(zip_data), 'zip_crc': 'PASS', 'internal_sha256_verified': len(records),
              'expanded_manifest_identical': True, 'final_report_identical': True,
              'local_zip_cleanup_permitted': True}
    (ROOT / 'deliveries/TASK010A_PUBLICATION_VERIFICATION.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
