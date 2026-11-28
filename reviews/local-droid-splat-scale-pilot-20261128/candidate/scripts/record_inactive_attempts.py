import json,pathlib
TASK=pathlib.Path(__file__).resolve().parents[1]
for name in ['SCALE_001','SCALE_A5_001']:
    run=TASK/'outputs'/name
    ev=[json.loads(x) for x in (run/'BA_CALLS.jsonl').read_text().splitlines()]
    fits=[r for e in ev for r in e['fit_records']]
    accepted=sum(r['accepted'] for r in fits)
    print(name,'accepted',accepted,'fits',len(fits))
    if accepted:raise RuntimeError('An active candidate cannot be excluded by this record')
    out=run/'CANDIDATE_NOT_ACTIVE.json'
    if out.exists():raise FileExistsError(out)
    out.write_text(json.dumps(dict(reason='ALL_FITS_IDENTITY_FALLBACK_SOURCE_GATE_ERROR',
        fits=len(fits),accepted=accepted,preserved_complete_trajectory=True),indent=2)+'\n')
