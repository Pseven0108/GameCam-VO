"""Export reviewable systems and receipts; full native traces remain separate."""
import pathlib,tarfile,json,io,hashlib,csv
import numpy as np
from analyze_native import ROOT,RECEIVER

SYSTEM_KEYS=['A','v','schur_subtraction','schur_rhs_subtraction','H_raw','rhs','L_damped_raw','dx']

def main():
    dest=ROOT/'05_analysis/reduced_native';dest.mkdir(exist_ok=True)
    receipt_root=ROOT/'04_results/states';receipt_root.mkdir(exist_ok=True)
    index=[];identities={}
    paths=sorted(RECEIVER.glob('result_*.tar'))+sorted(RECEIVER.glob('partial_*.tar'))
    for path in paths:
        complete=path.name.startswith('result_')
        state=path.stem.removeprefix('result_').removeprefix('partial_');out=receipt_root/state;out.mkdir(exist_ok=True)
        matrices={}
        proof=json.loads((RECEIVER/(path.stem+'.VERIFIED.json')).read_text())
        with tarfile.open(path,'r:') as archive:
            for member in archive:
                if not member.isfile():continue
                name=member.name.removeprefix('./')
                if pathlib.PurePosixPath(name).is_absolute() or '..' in pathlib.PurePosixPath(name).parts:
                    raise ValueError('Unsafe archive member')
                if name.endswith('.json'):
                    data=archive.extractfile(member).read();target=out/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
                    if name=='INPUT_IDENTITY.json':identities[state]=json.loads(data)
                selected=[u+'_'+c+'.npz' for u in ('FROZEN','NATIVE_UPDATE') for c in 'ABCD']
                selected.append('NATIVE_UPDATE_D_FAILED_ENDPOINT.npz')
                if name in selected:
                    tag=name[:-4]
                    with np.load(io.BytesIO(archive.extractfile(member).read()),allow_pickle=False) as values:
                        for it in (1,2):
                            for key in SYSTEM_KEYS:
                                matrices[tag+'_iter%d_'%it+key]=values['iter%d_'%it+key]
        reduced=dest/(state+'_SYSTEMS.npz');np.savez_compressed(reduced,**matrices)
        index.append({'state':state,'context_complete':complete,'native_trace_archive':path.name,
                      'native_trace_bytes':proof['archive_bytes'],
                      'native_trace_sha256':proof['archive_sha256'],
                      'release_asset':path.name,'reduced_systems':reduced.relative_to(ROOT).as_posix(),
                      'reduced_systems_sha256':hashlib.sha256(reduced.read_bytes()).hexdigest(),
                      'contains_full_C0_or_DINO_features':False,
                      'failed_endpoint_arrays_included':not complete,
                      'reduced_only_not_full_native_trace':True})
    comparisons=[]
    base=identities.get('D1_S1_RGB019')
    if base:
        for state,identity in identities.items():
            if identity['provenance']['rgb']!=19:continue
            for field,value in base['tensor_value_sha256'].items():
                comparisons.append({'state':state,'reference_state':'D1_S1_RGB019','tensor':field,
                                    'value_sha_equal':value==identity['tensor_value_sha256'][field],
                                    'intentional_origin_dependent_selected_prior':field=='selected_prior'})
    (dest/'INDEX.json').write_text(json.dumps({'states':index,'scope':'Small candidate-native matrices, rhs and dx, including the failed endpoint without implying validation. Complete per-round arrays are separate immutable assets. COMMON_INPUTS exists only for complete contexts; the failed input snapshot is preserved locally.'},indent=2))
    if comparisons:
        with (ROOT/'05_analysis/RGB019_CROSS_ORIGIN_HASH_COMPARISON.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(comparisons[0]));writer.writeheader();writer.writerows(comparisons)
    print(json.dumps({'states':len(index),'reduced_matrix_bytes':sum(p.stat().st_size for p in dest.glob('*.npz'))}))

if __name__=='__main__':main()
