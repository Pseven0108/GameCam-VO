"""Archive new task results only, including hashes of every original output."""
import argparse,hashlib,json,tarfile,shutil
from runtime import TASK,sha,write


def main():
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['cache','window']);p.add_argument('window');p.add_argument('--arm');a=p.parse_args()
    folder=TASK/('cache' if a.kind=='cache' else 'runs')/a.window
    if a.arm:folder/=a.arm
    assert folder.resolve().is_relative_to(TASK.resolve()) and folder.is_dir()
    label=a.kind+'_'+a.window+('_'+a.arm if a.arm else '')
    directory=TASK/'transfers';directory.mkdir(exist_ok=True)
    dest=directory/(label+'.tar.gz')
    if dest.exists():raise FileExistsError('Preserve transfer archive')
    files=[p for p in folder.rglob('*') if p.is_file()]
    if any(p.is_symlink() for p in folder.rglob('*')):raise RuntimeError('Unexpected output symlink')
    manifest=[dict(path=str(p.relative_to(folder)),sha256=sha(p),bytes=p.stat().st_size) for p in files]
    write(folder/'OUTPUT_SHA256.json',dict(files=manifest))
    with tarfile.open(dest,'w:gz',compresslevel=3) as t:t.add(folder,arcname='result',recursive=True)
    result=dict(archive=str(dest),source=str(folder),bytes=dest.stat().st_size,sha256=sha(dest),label=label)
    write(directory/(label+'.json'),result);print(json.dumps(result))


if __name__=='__main__':main()
