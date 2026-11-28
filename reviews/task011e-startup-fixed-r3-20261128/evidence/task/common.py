"""Independent TASK011D IO and source locks."""
import csv,hashlib,json,subprocess
from pathlib import Path

TASK=Path(__file__).resolve().parent
ROOT=TASK.parents[1]
BASE=Path('D:/aaa/GameCam-VO')
PARENT='ae5d98cf339b4ea867193362f384fe5a17737f26'
REVIEW_REL='reviews/task011e-fast-285-20261128'
REVIEW=ROOT/REVIEW_REL

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()

def dump(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def csvwrite(p,rows,fields=None):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    fields=fields or list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def initialize():
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=PARENT:raise RuntimeError('Wrong parent')
    target=TASK/'configs/FROZEN_SOURCE_LOCK.json'
    if target.exists():raise FileExistsError('Preserve existing stage')
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',PARENT,'experiments/TASK011B','experiments/TASK011C'],cwd=ROOT,text=True).splitlines()
    records=[]
    for rel in paths:
        p=ROOT/rel
        if not p.is_file():raise FileNotFoundError(p)
        raw=subprocess.check_output(['git','show',PARENT+':'+rel],cwd=ROOT)
        if p.read_bytes()!=raw:raise RuntimeError('Parent materialization differs')
        records.append(dict(path=rel,bytes=p.stat().st_size,sha256=sha(p)))
    dump(target,dict(parent_commit=PARENT,dependencies=records,production_baseline_modified=False))
    source=Path('C:/Users/Administrator/.codex/attachments/503309b0-9d6d-441d-babd-d3e9c95ffb66/已粘贴的文本.txt')
    (TASK/'intake').mkdir(exist_ok=True)
    (TASK/'intake/USER_INSTRUCTION.txt').write_bytes(source.read_bytes())
    dump(TASK/'intake/START_RECEIPT.json',dict(parent=PARENT,protected_files=len(records),stage=1,
        allowed='CPU + synthetic CUDA + later data preparation/framework',formal_SLAM_authorized=False))
    print('INITIALIZED',len(records))

if __name__=='__main__':initialize()
