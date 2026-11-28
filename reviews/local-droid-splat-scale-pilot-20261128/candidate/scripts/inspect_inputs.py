"""Read-only local inventory. Never connects to a remote machine."""
import csv, importlib.util, io, json, pathlib, platform, subprocess, sys, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROJECT = pathlib.Path('D:/aaa/GameCam-VO')

def main():
    out = {'platform': platform.platform(), 'python': sys.executable}
    cam = PROJECT / 'audits/VIPER_R0_1_TRAIN_AND_VO_PROTOCOL_AUDIT/02_metadata/train_camera.zip'
    with zipfile.ZipFile(cam) as z:
        out['camera_members'] = z.namelist()[:10]
        name = next(n for n in z.namelist() if n.endswith('001.csv'))
        rows = list(csv.DictReader(io.StringIO(z.read(name).decode('utf-8-sig'))))
        out['camera_example'] = {'member': name, 'rows': len(rows), 'first': rows[0]}
    roots = [PROJECT / 'downloads/VIPER_RGB_JPG_ORIGINALS_20261119/archives',
             pathlib.Path('C:/Users/Administrator/Downloads')]
    out['archives'] = [dict(path=str(p), bytes=p.stat().st_size)
                       for root in roots if root.exists() for p in root.glob('*jpg*.zip')]
    candidates = [pathlib.Path('D:/aaa/GameCam-VO-TASK009/external/DROID-W'),
                  PROJECT / 'baselines/droid_w/upstream']
    out['source_candidates'] = []
    for p in candidates:
        if p.exists():
            out['source_candidates'].append(dict(path=str(p), head=subprocess.check_output(
                ['git','-C',str(p),'rev-parse','HEAD'], text=True).strip()))
    print(json.dumps(out, indent=2))

if __name__ == '__main__': main()
