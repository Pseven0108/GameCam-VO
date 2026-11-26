"""Materialize reviewed Linux wheels using host filesystem I/O, into D: only.

WSL /mnt/d extraction of tens of thousands of small files is very slow. No
package import/installation script is executed by this utility. This does not
install Linux wheels into the Windows environment.
"""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path, PurePosixPath

root = Path(__file__).resolve().parents[3]
prefix = root / 'runtime/wsl310'
site = prefix / 'lib/python3.10/site-packages'
assert str(site).startswith('D:\\aaa\\GameCam-VO-TASK009\\runtime\\')
receipts = []
receipt_path = root / 'experiments/TASK009/intake/linux_host_materialization.json'
previous = json.loads(receipt_path.read_text())['wheels'] if receipt_path.exists() else []
previous_by_name = {r['wheel']: r for r in previous}
for wheel in sorted((root / 'runtime/linux-wheels').glob('*.whl')):
    if wheel.name.startswith('markupsafe-3.0.3-'):
        continue  # 3.0.4 is the selected resolver output.
    if wheel.name.startswith(('setuptools-', 'wheel-')):
        continue  # Preserve the existing working build frontend.
    if wheel.name in previous_by_name:
        receipts.append(previous_by_name[wheel.name])
        continue
    h = hashlib.sha256()
    with wheel.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    count = 0
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            p = PurePosixPath(info.filename)
            if p.is_absolute() or '..' in p.parts:
                raise ValueError('Unsafe wheel member')
            if info.is_dir():
                continue
            parts = p.parts
            if parts[0].endswith('.data'):
                scheme, *rest = parts[1:]
                base = {'purelib': site, 'platlib': site, 'scripts': prefix / 'bin',
                        'data': prefix, 'headers': prefix / 'include'}.get(scheme)
                if base is None:
                    raise ValueError(f'Unsupported wheel scheme: {scheme}')
                target = base.joinpath(*rest)
            else:
                target = site.joinpath(*parts)
            if not target.resolve().is_relative_to(prefix.resolve()):
                raise ValueError('Destination escapes runtime')
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, target.open('wb') as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
            count += 1
    receipts.append({'wheel': wheel.name, 'sha256': h.hexdigest(), 'members': count})
    print(wheel.name, count, flush=True)
receipt_path.write_text(
    json.dumps({'prefix': str(prefix), 'method': 'host streaming wheel materialization',
                'wheels': receipts}, indent=2))
