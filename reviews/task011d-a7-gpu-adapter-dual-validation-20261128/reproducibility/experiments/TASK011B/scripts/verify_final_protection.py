"""Re-read historical identities and frozen assets; never load a checkpoint."""
import json,shlex,subprocess
from pathlib import Path
from common import ROOT,TASK,dump,sha
from remote_transport import SSH,options


def main():
    original=ROOT/'reviews/task011b-validity-aware-cadp-dr-20261127/10_FINAL_REPORT/ORIGINAL_ASSET_PROTECTION.json'
    expected=json.loads(original.read_text())['files'];checked=[]
    for row in expected:
        p=Path(row['path']);identity=sha(p)
        if identity!=row['sha256']:raise RuntimeError('Historical local asset changed: '+row['kind'])
        checked.append(dict(**row,final_sha256=identity,final_unchanged=True))
    frozen=Path('D:/aaa/GameCam-VO/experiments/DROID_W_TASK003_VAL007_OBSERVATION_R1/remote/incoming/native_config.yaml')
    if sha(frozen)!=sha(TASK/'configs/frozen_r2.yaml'):raise RuntimeError('R2 YAML changed')
    raw=json.loads((TASK/'private/remote/ORIGINAL_FOUR_WEIGHT_SHA_001.stdout').read_text())
    native='/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/source/DROID-W/droid_backends.cpython-310-x86_64-linux-gnu.so'
    raw[native]='6dcf8de36cadc2174023b649b026f04e61b1231420d98763cc5aa3b294a91c3e'
    candidate_identity=json.loads((TASK/'intake/CANDIDATE_BINARY_MIDBATCH_IDENTITY.json').read_text())
    raw[candidate_identity['path']]=candidate_identity['sha256']
    exported=json.loads((TASK/'intake/FORMAL_SOURCE_BLOB_AUDIT.json').read_text())
    ending=json.loads((TASK/'intake/FORMAL_SOURCE_LINE_ENDING_AUDIT.json').read_text())
    if ending['non_line_ending_differences'] or ending['raw_identical_files']+ending['CRLF_only_files']!=208:
        raise RuntimeError('Exported source is not the frozen upstream content')
    source_expected={r['path']:r['actual_blob'] for r in exported['files']}
    code='''import hashlib,json
from pathlib import Path
expected=EXPECTED
rows=[]
for name,identity in expected.items():
 p=Path(name);h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 assert h.hexdigest()==identity,'Protected asset hash changed'
 rows.append(dict(path=name,bytes=p.stat().st_size,sha256=h.hexdigest(),unchanged=True))
source_root=Path('/root/rivermind-data/GAMECAM_TASK011B_20261127_AMP_NATIVE_R2/source/DROID-W')
source_rows=[]
for name,identity in SOURCE_EXPECTED.items():
 p=source_root/name;h=hashlib.sha1();h.update(('blob '+str(p.stat().st_size)+'\\0').encode())
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024**2),b''):h.update(b)
 assert h.hexdigest()==identity,'Exported runtime source changed'
 source_rows.append(dict(path=name,actual_git_blob=identity,unchanged=True))
print(json.dumps(dict(weights=rows,source=source_rows)))
'''.replace('SOURCE_EXPECTED',repr(source_expected)).replace('EXPECTED',repr(raw))
    p=subprocess.run([str(SSH),'-T','-p','31454',*options(),'root@sc01-ssh.gpuhome.cc',
        '/usr/bin/python3 -B -'],input=code.encode(),capture_output=True,timeout=240)
    if p.returncode:raise RuntimeError('Remote final protection check failed')
    remote_value=json.loads(p.stdout);remote=remote_value['weights']
    head=subprocess.check_output(['git','-C','D:/aaa/GameCam-VO-TASK009/external/DROID-W','rev-parse','HEAD'],text=True).strip()
    if not head.startswith('c3414af6047d'):raise RuntimeError('Frozen source HEAD changed')
    # Check task candidate files against their sealed source provenance.
    provenance=json.loads((TASK/'CADP_DR_EXPERIMENTAL_BRANCH/SOURCE_PROVENANCE.json').read_text())
    for row in provenance['sources']:
        if sha(TASK/'CADP_DR_EXPERIMENTAL_BRANCH/native'/row['file'])!=row['candidate_sha256']:
            raise RuntimeError('Candidate native source changed after preparation')
    value=dict(status='PASS',local_historical_files=len(checked),local_files=checked,
        remote_original_weights_and_installed_extension=remote,original_source_head=head,
        remote_exported_runtime_source_final_unchanged=remote_value['source'],
        upstream_content_line_ending_admission=dict(raw_identical_files=ending['raw_identical_files'],CRLF_only_files=ending['CRLF_only_files'],non_line_ending_differences=0),
        candidate_binary_identity_checked_since_midbatch_only=True,
        frozen_R2_yaml_sha256=sha(frozen),original_configuration_changed=False,
        model_weights_deserialized=False,all_checkpoint_files_read_only=True,
        original_cuda_extension_recompiled_or_replaced=False)
    dump(TASK/'intake/FINAL_ORIGINAL_ASSET_PROTECTION.json',value)
    print('FINAL_PROTECTED_ASSETS_UNCHANGED',len(checked),len(remote),flush=True)


if __name__=='__main__':main()
