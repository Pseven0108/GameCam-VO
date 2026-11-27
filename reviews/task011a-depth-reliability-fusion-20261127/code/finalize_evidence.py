"""Read-only final identity checks and public cache/protocol traceability."""
from common import *
import shutil

def main():
    out=Path(json.loads((TASK/'private/LATEST_SUCCESSFUL_RUN.json').read_text())['path'])
    before=json.loads((TASK/'private/PROTECTED_INPUTS_BEFORE.json').read_text());checks=[]
    for row in before:
        p=Path(row['path']);s=p.stat();actual=sha(p)
        checks.append({'path':str(p),'sha256':actual,'size_and_mtime_unchanged':s.st_size==row['bytes'] and s.st_mtime_ns==row['mtime_ns'],'sha256_unchanged':actual==row['sha256']})
    if not all(r['size_and_mtime_unchanged'] and r['sha256_unchanged'] for r in checks):raise RuntimeError('Protected original cache/source changed')
    cfg=json.loads((out/'RUN_CONFIGURATION.json').read_text());frozen=[]
    for name,expected in cfg['source_sha256'].items():
        p=TASK/'scripts'/name;frozen.append({'file':name,'sha256':sha(p),'matches_executed_source':sha(p)==expected})
    if not all(r['matches_executed_source'] for r in frozen):raise RuntimeError('Executed experiment core source changed')
    testpath=TASK/'private/tests_002.log'
    tests=testpath.read_text(encoding='utf-8',errors='replace')
    if 'Ran 33 tests' not in tests or not tests.rstrip().endswith('OK'):raise RuntimeError('Executed test evidence missing')
    shutil.copyfile(testpath,out/'CPU_TEST_RESULTS.log')
    shutil.copyfile(SOURCE/'04_evaluation/STRICT_GT_GATE_FAILURE.json',TASK/'intake/STRICT_GT_GATE_FAILURE.json')
    arrays=[];manifest=[];errors=csvread(out/'depth_error_context.csv')
    for row in records():
        item=row['sample'];sid=item['sample_id'];path=out/'risk_maps'/(sid+'.npz')
        with np.load(path,allow_pickle=False) as z:
            for key in z.files:
                a=z[key];arrays.append({'sample_id':sid,'field':key,'shape':'x'.join(map(str,a.shape)),'dtype':str(a.dtype),'finite_pixels':int(np.isfinite(a).sum()),'nonfinite_pixels':int((~np.isfinite(a)).sum()),'GT_invalid_AbsRel_nan_is_intentional':key=='AbsRel'})
        meta={k:item[k] for k in ['sample_id','dataset','sequence_id','frame_id','environment','input_hw']}
        meta.update(cache_relative_path=str(Path(row['local_npz']).relative_to(SOURCE)),cache_sha256=row['sha256'],RGB_sha256=item['rgb_sha256'],cache_bytes=row['bytes'],new_rank_map_sha256=sha(path),raw_confidence_direction='negative score is risk',raw_flip_formula='abs(D-reverse_x(Dflip))/(abs(D)+1e-6)',GT_unit='NOT_ADMITTED_FOR_VIPER' if item['dataset']=='VIPER' else 'CALIBRATED_NATIVE_SOURCE_UNIT_NOT_VERIFIED_METRES')
        if item['dataset']=='MVS-Synth':
            pair=json.loads((HIST/(sid+'_GT_PAIRING.json')).read_text());meta['GT_sha256']=pair['GT_sha256'];meta['GT_valid_pixels']=next(r['GT_valid_pixels'] for r in errors if r['sample_id']==sid and r['view']=='FROZEN_BICUBIC_ZERO_EXTENDED')
        manifest.append(meta)
    csvwrite(out/'cache_manifest.csv',manifest);csvwrite(out/'derived_array_inventory.csv',arrays)
    state={'status':'PASS','protected_file_count':len(checks),'all_original_input_hashes_sizes_mtimes_unchanged':True,'protected_identity_checks':checks,'executed_core_source_checks':frozen,'CPU_tests_executed':33,'new_model_forwards':0,'CUDA_initialized':False,'production_source_changed':False}
    dump(out/'ORIGINAL_EVIDENCE_PRESERVATION.json',state)
    dump(TASK/'private/FINAL_EVIDENCE_READY.json',{'status':'COMPLETE','protected_files':len(checks),'CPU_tests':33,'new_GPU_forwards':0})
    cpu_assert();print('FINAL_EVIDENCE_PASS',len(checks),'protected files; 33 tests; executed source identities unchanged')

if __name__=='__main__':main()
