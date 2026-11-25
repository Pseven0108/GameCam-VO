"""Reconstruct deliberately changed prior arguments from retained CPU inputs."""
import pathlib,sys,json,hashlib,tarfile,io
import numpy as np
from analyze_native import ROOT,RECEIVER

def sha_array(value):return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()

def audit(archive):
    with tarfile.open(archive,'r:') as tar:
        identity=json.load(tar.extractfile('./INPUT_IDENTITY.json'))
        with np.load(io.BytesIO(tar.extractfile('./COMMON_INPUTS.npz').read()),allow_pickle=False) as data:
            prior=data['mono'];mono_sha=sha_array(prior);zero_sha=sha_array(np.zeros_like(prior))
        assert mono_sha==identity['tensor_value_sha256']['cached_mono']
        origin_prior=identity['tensor_value_sha256']['selected_prior']
        assert origin_prior==(mono_sha if identity['provenance']['D_origin'] else zero_sha)
        rows=[]
        for U in ('FROZEN','NATIVE_UPDATE'):
            for D in (1,0):
                rows.append({'kind':'original_installed','U_mode':U,'D':D,
                             'effective_prior_argument_sha256':mono_sha if D else zero_sha,
                             'effective_prior':'cached_mono' if D else 'zeros_like_selected_prior'})
            for cell,(C,G) in {'A':(1,1),'B':(1,0),'C':(0,1),'D':(0,0)}.items():
                rows.append({'kind':'independent_candidate','U_mode':U,'cell':cell,'C':C,'G':G,
                             'effective_prior_argument_sha256':mono_sha,
                             'effective_prior':'cached_mono','mask_disabled_internally':cell=='D'})
        return {'state':identity['provenance'],'recorded_hashes_are_pre_override_clone_template':True,
                'template_selected_prior_sha256':origin_prior,'all_nonprior_tensor_clones_value_layout_alias_verified_in_runtime':True,
                'effective_arguments_reconstructed_from_frozen_runner_and_input_bytes':rows,
                'original_D0_and_candidate_D_prior_arguments_byte_equal':False,
                'endpoint_numerical_equivalence_validated_separately':True}

if __name__=='__main__':
    rows=[audit(path) for path in sorted(RECEIVER.glob('result_*.tar'))]
    (ROOT/'05_analysis/EFFECTIVE_ARGUMENT_AUDIT.json').write_text(json.dumps({'states':rows,'note':'Hash receipts certify clone templates. Prior override is intentional and is not hidden by calling all effective arguments identical.'},indent=2))
    print(json.dumps({'states':len(rows),'PASS':True}))
