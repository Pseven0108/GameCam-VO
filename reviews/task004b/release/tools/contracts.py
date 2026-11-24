"""Read-only Task004 A contracts, shared by the scheduler and verifier."""
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORDER = ('E3', 'E4', 'E7', 'E0', 'E8', 'E6', 'E1', 'E2')
BITS = dict(E0=(1, 1, 1), E1=(0, 1, 1), E2=(1, 0, 1), E3=(1, 1, 0),
            E4=(0, 0, 1), E6=(0, 1, 0), E7=(1, 0, 0), E8=(0, 0, 0))
POLICY_SHA = dict(zip(ORDER, (
    'd91c5a0c6a702f86f3d81e8623088ac7dd787df6efa5a70acb4e4156a9e2a4ca',
    '55ba54a86e3938158fb4910532b65c26b1fb0919b84ce253819470560d6b4d8e',
    'b969b0207f0d458dcfd351d3ee8b0fd217c051986c87ab2b03b895b53ea71099',
    '242cd6248dea4186b803b5c45d4e7838825f6bc9bd1ba92f6d79b241d12e4500',
    '64974dcb64b819d26c7bb725d9c55ecc7c77bfcf7597ffcdf57fb4f3332025ed',
    '6e2df5994153531597ca43be109a5ca80acd510389c090d049353271c47dff8d',
    'fbc8a69b5480b2c2984829f05180b8006504e1744b91c99a9993539fea918640',
    '7ef39b96a69139a4a2d07d404d3cdbb37516f4bff5d8ac520529e1b0d5f6eb85',
)))
SEGMENT = 'val_007_full_00001-00487'
COMMIT = 'c3414af6047d06bafc1a6645d09f23247f3b2cdc'
CONFIG_SHA = 'a213d74874ad953000dde6b7506694b369fad9b2eaccaff58f063accdfbb50fc'
INPUT_SHA = '5547cdd407e022ba27a8b9af18f1ef4e9471ea58c1e0df96aec38fee180aa537'
TENSOR_SHA = '2e27f696f9553821d1e43cdd673118c90e3932904b9df652d887105f04fbb26a'
GT_SHA = '91fb149c066bb488ac6071602a4b50fe1540243f2db3369a3706f63b705d7008'
PUBLISHED_ZIP_SHA = 'b1456d04398a628fdbc50743d6f0a0be87e3cd79e32d39d1c4ac3a78ad2f1684'
R2_K = [386.01129150390625, 386.01129150390625, 319.5, 179.5]
IDS = tuple(range(1, 488))
TARGET = (312, 328)
S_REF = 19.1341794347
PORTS = (9875, 9876, 9877)
LOCAL_STAGES = ('frontend_local_predecision', 'frontend_local_retained')
GIB = 1024**3
DISK_FLOOR = 10 * GIB
ARM_BUDGET = 3 * GIB
DISK_ADMISSION = DISK_FLOOR + ARM_BUDGET


def need(condition, message):
    if not condition:
        raise ValueError(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def stat_sha(path):
    with Path(path).open('rb') as stream:
        return stream_sha(stream)


def stream_sha(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(2**20), b''):
        digest.update(chunk)
    return digest.hexdigest()


def pairs(items):
    out = {}
    for key, value in items:
        need(key not in out, f'duplicate JSON key: {key}')
        out[key] = value
    return out


def strict_json(raw):
    def reject(value):
        raise ValueError(f'invalid JSON number {value}')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject)


def read_json(path):
    return strict_json(Path(path).read_bytes())


def new_json(path, doc):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(doc, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def write_csv(path, fields, rows):
    with Path(path).open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def verify_policy(path, arm):
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    need(digest == POLICY_SHA[arm], f'{arm}: policy SHA-256 mismatch')
    doc = strict_json(raw)
    need(doc == dict(schema='GAMECAM_TASK004_PHASE_POLICY_V1', base_config_sha256=CONFIG_SHA,
                     campaign='FACTORIAL', arm=arm, local_dwu=list(BITS[arm]), final_phases=2),
         f'{arm}: unexpected policy contents')
    return digest


def verify_matrix(assets):
    path = Path(assets) / 'TASK004_FACTORIAL_MATRIX.csv'
    with path.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    need(len(rows) == len(ORDER) and {r['arm'] for r in rows} == set(ORDER), 'matrix arm inventory mismatch')
    for row in rows:
        arm = row['arm']
        need(tuple(int(row[k]) for k in ('D', 'W', 'U')) == BITS[arm]
             and int(row['screening_slot']) == ORDER.index(arm) + 1 and row['seed'] == '43'
             and row['policy_file'] == f'policies/{arm}.json'
             and row['policy_sha256'] == POLICY_SHA[arm], f'{arm}: matrix contract mismatch')
        verify_policy(Path(assets) / row['policy_file'], arm)
    return rows


def history_inputs(parent):
    """Verify the actual Task004 review archive before deriving reusable release assets."""
    from zipfile import ZipFile

    ref = Path(parent) / 'GAMECAM_TASK004_CAUSAL_ABLATION_REVIEW.zip'
    outer = stat_sha(ref)
    need(outer == PUBLISHED_ZIP_SHA, 'Task004 archive identity changed')
    with ZipFile(ref) as archive:
        names = archive.namelist()
        need(len(names) == len(set(names)) == 80 and archive.testzip() is None, 'Task004 ZIP CRC/member failure')
        doc = strict_json(archive.read('FILE_SHA256_MANIFEST.json'))
        payload = doc['files']
        need(set(names) == set(payload) | {'FILE_SHA256_MANIFEST.json'}, 'Task004 manifest coverage mismatch')
        data = {}
        for name, expected in payload.items():
            raw = archive.read(name)
            need(len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == expected['sha256'], name)
            if name in ('TASK004_FACTORIAL_MATRIX.csv', 'evidence/SOURCE_AND_CANDIDATE_IDENTITY.json') or name.startswith(('policies/', 'candidates/')):
                data[name] = raw
    return data, dict(path=str(ref), archive_sha256=outer, members=len(names), payload_matches=len(payload), crc='PASS')
