"""Task-local, CPU-only evidence IO. Historical assets are read-only inputs."""
import csv
import hashlib
import json
from pathlib import Path

TASK = Path(__file__).resolve().parent
ROOT = TASK.parents[1]
BASE = Path('D:/aaa/GameCam-VO')
PARENT = '78ca580c636bb232eba6d46ccf704b193988b5ab'
REVIEW_REL = 'reviews/task011c-maxfusion-spatial-utility-20261128'
REVIEW = ROOT / REVIEW_REL


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            digest.update(block)
    return digest.hexdigest()


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def csvwrite(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
