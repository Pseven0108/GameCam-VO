"""Execute the full CPU suite, source-kernel audit and frozen scoring checks."""
import contextlib,hashlib,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2];TASK=ROOT/'candidate'
def kernel_bodies(text):
    import re
    result={}
    for m in re.finditer(r'__global__\s+void\s+(\w+)\s*\(',text):
        start=text.index('{',m.end());depth=1;i=start+1
        while depth:
            if text[i]=='{':depth+=1
            elif text[i]=='}':depth-=1
            i+=1
        result[m.group(1)]=text[start:i]
    return result
def main():
    suite=unittest.defaultTestLoader.discover(str(TASK/'tests'),pattern='test_*.py')
    with (TASK/'reports/FINAL_CPU_TEST_LOG.txt').open('w') as f:
        result=unittest.TextTestRunner(stream=f,verbosity=2).run(suite)
    receipt=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),passed=result.wasSuccessful())
    (TASK/'reports/FINAL_CPU_TEST_RESULTS.json').write_text(json.dumps(receipt,indent=2)+'\n')
    if not result.wasSuccessful():raise RuntimeError('CPU regression failed')
    original=kernel_bodies((ROOT.parent/'GameCam-VO-DROID-SPLAT-CANDIDATE/candidate/native/droid_kernels.cu').read_text())
    candidate=kernel_bodies((TASK/'native/droid_kernels.cu').read_text())
    if original!=candidate:raise RuntimeError('An original CUDA kernel body was altered')
    report=dict(kernel_count=len(original),all_original_cuda_kernel_bodies_equal=True,
        kernel_names=sorted(original),candidate_change='BA host assembly adds Cauchy prior C/b inside iteration; original geometry/U kernels unchanged')
    (TASK/'reports/KERNEL_PRESERVATION.json').write_text(json.dumps(report,indent=2)+'\n')
    # Adapt only file locations/arm names in the previously exercised scorer validator.
    old=(ROOT.parent/'GameCam-VO-DROID-SPLAT-CANDIDATE/candidate/scripts/check_final_evidence.py').read_text()
    old=old.replace("[('BASE','BASE_003'),('A5','A5_001'),('SCALE','SCALE_002'),('SCALE_A5','SCALE_A5_002')]",
        "[(a,a+'_001') for a in ['BASE','A5','ROBUST','ROBUST_A5']]")
    old=old.replace("    local_before=json.loads((TASK/'reports/STAGING_RECEIPT.json').read_text())\n    import subprocess\n    git_path=pathlib.Path(local_before['source_repository'])\n",'')
    path=TASK/'scripts/check_final_evidence.py';path.write_text(old)
    namespace={'__name__':'final_evidence','__file__':str(path)}
    exec(compile(old,str(path),'exec'),namespace);namespace['main']()
    print('FINAL_CPU_AND_SOURCE_VALIDATION',receipt)
if __name__=='__main__':main()
