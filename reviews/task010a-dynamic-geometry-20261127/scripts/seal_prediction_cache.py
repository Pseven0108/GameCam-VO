"""Sidecar identities for model caches; original receipts stay intact."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
for model in ['gmos','pi3mos','geomotion','geomotion_full']:
    directory=TASK/'outputs'/model
    for out in directory.glob('*') if directory.exists() else []:
        receipt=out/'receipt.json'
        if not receipt.exists() or json.loads(receipt.read_text()).get('status')!='COMPLETE':continue
        entries={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob('*.npz'))}
        sidecar=out/'PREDICTION_SHA256.json'
        if sidecar.exists() and json.loads(sidecar.read_text())!=entries:raise ValueError('Sealed prediction changed')
        if not sidecar.exists():sidecar.write_text(json.dumps(entries,indent=2))
        print(model,out.name,len(entries))
