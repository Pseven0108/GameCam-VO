"""Local, CPU-only access to immutable Task 002B inputs."""

import csv
import hashlib
import io
import json
import os
import sys
from pathlib import Path
from zipfile import ZipFile

OUT = Path(__file__).resolve().parents[1]
EXP = OUT.parent
R2 = EXP / 'VIPER_MATCHED_DUAL_BASELINE_R2'
R1 = EXP / 'DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1'
ZIP = R2 / 'evaluation/VIPER_MATCHED_DUAL_BASELINE_R2_REVIEW_PACKAGE.zip'
TASK_A = EXP / ('DROID_W_TASK002A_ABLATION_SWITCH_DEPENDENCY_AUDIT/'
                'CHAT_REVIEW_PACKAGE/GAMECAM_DROID_W_TASK002A_REVIEW.zip')
AUDIT1 = EXP / 'DROID_SLAM_DROID_W_TASK001_STATIC_AUDIT/evidence'
SOURCES = EXP / 'DROID_SLAM_TO_DROID_W_SOURCE_DIFF_EVIDENCE_MAPPING_R1/sources'
FROZEN_NAME = 'VIPER_R2_FROZEN_VAL92_MANIFEST.csv'
LOCK_NAME = 'VIPER_R2_PROTOCOL_LOCK.json'
RAW_ROOT = EXP.parent / 'downloads/VIPER_RGB_JPG_ORIGINALS_20261119/archives'
ZIP_SHA = '582c778c5649d13b06d0f8ac16160441c37b06f5eb6dd644a1279393d6162315'
EVAL_SHA = 'be1a605d1a0fbfa22db61ae7f4eabbde080bb12ce01110ee8f2684aeaefc477e'
COMMITS = {'DROID-SLAM': '2dfd39f0dcad44012ca7bbb8aa70b55edbfa9c99',
           'DROID-W': 'c3414af6047d06bafc1a6645d09f23247f3b2cdc'}
FIXED, VIRTUAL = 'FIXED_K_NATIVE_RESIZE', 'VIRTUAL_K_DIRECT_REMAP'
ENVIRONMENTS = ('Day', 'Sunset', 'Rain', 'Night', 'Snow')
OFFSETS = (1, 15, 60, 150)
INPUT_PRECHECK = 'evidence/IMMUTABLE_INPUT_WORKLIST.json'


def cpu_guard():
    # On Windows an empty shell assignment may remove the environment entry.
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    os.environ['OMP_NUM_THREADS'] = '2'
    os.environ['OPENBLAS_NUM_THREADS'] = '1'
    os.environ['MKL_NUM_THREADS'] = '1'
    sys.dont_write_bytecode = True


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read_json(path):
    return json.loads(Path(path).read_bytes())


def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def csv_bytes(data):
    return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))


def require(value, description):
    if not value:
        raise ValueError(description)


def save_json(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + '\n',
                            encoding='utf-8')


def save_csv(name, records, fields=None):
    records = list(records)
    fields = fields or list(dict.fromkeys(k for row in records for k in row))
    with (OUT / name).open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(records)


def exact_member(archive, member, local=None):
    path = local or R2 / member
    data = path.read_bytes()
    require(data == archive.read(member), f'current bytes differ from original R2 ZIP: {path}')
    return data


def verify_package():
    require(ZIP.stat().st_size == 10_653_960 and digest(ZIP) == ZIP_SHA, 'original R2 ZIP identity failed')
    with ZipFile(ZIP) as z:
        require(z.testzip() is None, 'original R2 ZIP CRC failed')
        require(len(set(z.namelist())) == len(z.infolist()), 'duplicate original R2 ZIP members')
        count = len(z.infolist())
    return count


def load_contract(z):
    lock_data = exact_member(z, 'PROTOCOL_LOCK.json', R2 / LOCK_NAME)
    require(lock_data == (R2 / 'PROTOCOL_LOCK.json').read_bytes(), 'protocol aliases differ')
    manifest_data = exact_member(z, FROZEN_NAME)
    with ZipFile(TASK_A) as a:
        require(a.read(f'evidence/R2/{LOCK_NAME}') == lock_data, 'Task 002A lock differs')
        require(a.read(f'evidence/R2/{FROZEN_NAME}') == manifest_data, 'Task 002A manifest differs')
    lock = json.loads(lock_data)
    manifest = csv_bytes(manifest_data)
    require(sha(manifest_data) == lock['manifest_sha256'], 'frozen CSV digest differs from protocol')
    require(lock['protocol'] == 'VIPER_MATCHED_DUAL_BASELINE_R2_V1' and lock['stride'] == 1
            and lock['image_wh'] == [640, 360] and lock['evaluation']['rpe_offsets'] == list(OFFSETS)
            and lock['evaluation']['sample_nominal_fps'] == 15 and lock['evaluation']['source_sha256'] == EVAL_SHA
            and lock['slam_commit'] == COMMITS['DROID-SLAM'] and lock['wild_commit'] == COMMITS['DROID-W'],
            'unexpected protocol, commits or evaluator')
    require(len(manifest) == len({r['id'] for r in manifest}) == lock['segments'] == 92, 'frozen segment count')
    require(len({r['sequence'] for r in manifest}) == lock['sequences'] == 47, 'frozen sequence count')
    require(sum(int(r['frames']) for r in manifest) == lock['frames'] == 49_815, 'frozen frame count')
    for branch, rows, seqs in [(FIXED, 82, 45), (VIRTUAL, 10, 2)]:
        group = [r for r in manifest if r['branch'] == branch]
        require(len(group) == rows and len({r['sequence'] for r in group}) == seqs, 'frozen branch count')
    return lock, manifest
