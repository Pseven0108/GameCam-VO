"""Shared file formats; no model dependencies."""

import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIB = 1024**3
SEGMENT_ID = re.compile(r"(?:train|val)_\d{3}_(?:full|pilot)_\d{5}-\d{5}\Z")
DROID_W_COMMIT = "c3414af6047d06bafc1a6645d09f23247f3b2cdc"
ENVIRONMENTS = ("Day", "Sunset", "Rain", "Night", "Snow")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + ".partial")
    tmp.write_text(json.dumps(value, allow_nan=False, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def csv_write(path, columns, iterable):
    path = Path(path)
    tmp = path.with_name(path.name + ".partial")
    with tmp.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(iterable)
    tmp.replace(path)


def rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)
