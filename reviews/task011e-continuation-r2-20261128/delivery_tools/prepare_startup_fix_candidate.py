"""Prepare a CPU-tested, unapplied import-isolation candidate; no model retry."""
import json, shutil
from pathlib import Path

BASE=Path(__file__).resolve().parent
def main():
    original=BASE/'repo/experiments/TASK011E'
    candidate=BASE/'startup_import_fix_candidate'
    candidate.mkdir(exist_ok=False)
    helper='''"""Stage-local IO identity, independent of generic common module imports."""
import hashlib
from pathlib import Path
TASK=Path(__file__).resolve().parent
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024**2),b''):h.update(block)
    return h.hexdigest()
'''
    (candidate/'task011e_io.py').write_text(helper,encoding='utf-8')
    for name in ('authorization.py','native_binding.py'):
        raw=(original/name).read_text(encoding='utf-8')
        assert raw.count('from common import TASK,sha')==1
        raw=raw.replace('from common import TASK,sha','from task011e_io import TASK,sha')
        (candidate/name).write_text(raw,encoding='utf-8')
    print(json.dumps(dict(status='UNAPPLIED_CANDIDATE_PREPARED',files=3,
                         original_attempt_modified=False,GPU_retry=False)))
if __name__=='__main__':main()
