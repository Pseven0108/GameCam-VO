"""Add a separately named Full-GeoMotion gate without altering ongoing v1 runs."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
scripts=TASK/'scripts';dest=TASK/'09_reproducibility/source_versions/v2_transfer'
dest.mkdir(parents=True,exist_ok=True)
source=(scripts/'run_window.py').read_text()
source=source.replace("'gmos','geomotion','geometry'","'gmos','geomotion','geomotion_full','geometry'")
source=source.replace('from task010_fusion import install_observer, install_fusion','from task010_fusion_v2 import install_observer, install_fusion')
source=source.replace("'scripts/task010_fusion.py'","'scripts/task010_fusion_v2.py'")
source=source.replace("ROOT/'experiments/TASK010-A/scripts/task010_fusion.py'","ROOT/'experiments/TASK010-A/scripts/task010_fusion_v2.py'")
(scripts/'run_window_v2.py').write_text(source)
fusion=(scripts/'task010_fusion.py').read_text()
fusion=fusion.replace("model='geomotion' if method=='geomotion' else", "model=method if method in ('geomotion','geomotion_full') else")
(scripts/'task010_fusion_v2.py').write_text(fusion)
records={}
for name in ['run_window_v2.py','task010_fusion_v2.py','native_forkserver_controller.py','task010_native_preload.py','run_native.sh']:
    data=(scripts/name).read_bytes();(dest/name).write_bytes(data)
    records[name]=hashlib.sha256(data).hexdigest()
(dest/'SHA256.json').write_text(json.dumps(records,indent=2))
print('v2 separate source frozen; v1 source and active plan untouched')
