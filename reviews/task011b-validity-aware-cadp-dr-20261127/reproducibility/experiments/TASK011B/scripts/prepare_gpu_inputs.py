"""Materialize no-pose GPU inputs and exact upstream source from local Git."""
import csv,io,json,subprocess,tarfile
from pathlib import Path
from common import ROOT,TASK,dump,sha


def main():
    source=Path('D:/aaa/GameCam-VO-TASK009/external/DROID-W')
    raw=subprocess.check_output(['git','-C',str(source),'archive','c3414af6047d06bafc1a6645d09f23247f3b2cdc'])
    # Entire tracked upstream source, never local compatibility diffs or weights.
    bundle=TASK/'private/upstream_c3414af6.tar.gz'
    import gzip
    bundle.write_bytes(gzip.compress(raw))
    paths=json.loads((TASK/'private/VIPER_INPUTS.json').read_text())['windows']
    integrity=list(csv.DictReader((TASK/'private/viper_inputs/RGB_INTEGRITY.csv').open()))
    rows=[]
    for window in paths:
        items=[r for r in integrity if r['window']==window['window_id']]
        rows.append(dict(window_id=window['window_id'],sequence=window['sequence'],environment=window['environment'],
            K_640x360=window['K_640x360'],frames=[dict(rgb_id=int(r['rgb_id']),sha256=r['sha256'],bytes=int(r['bytes'])) for r in items]))
    dump(TASK/'configs/GPU_RGB_INPUTS.json',dict(windows=rows,GT_poses_included=False))
    original=Path('D:/aaa/GameCam-VO/experiments/DROID_W_TASK003_VAL007_OBSERVATION_R1/remote/incoming/native_config.yaml')
    (TASK/'configs/frozen_r2.yaml').write_bytes(original.read_bytes())
    print(json.dumps(dict(upstream_tar_bytes=bundle.stat().st_size,sha256=sha(bundle),windows=len(rows))))


if __name__=='__main__':main()
