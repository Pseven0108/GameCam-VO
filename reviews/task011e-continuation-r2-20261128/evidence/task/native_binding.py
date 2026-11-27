"""Hash-verified existing TASK011B extension, never rebuilt or overwritten."""
import importlib.util,json,os,subprocess
from pathlib import Path
from common import TASK,sha

def verify_upstream_source():
    root=Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/source/DROID-W')
    lock=json.loads((TASK/'configs/UPSTREAM_PYTHON_IDENTITY.json').read_text())
    if (root/'.git').exists():
        commit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    else:
        # The official fresh deployment is an archive, not a Git checkout.
        # Use its sealed archive provenance AND every locked Python/config file.
        provenance=json.loads((root/'.official_archive.json').read_text())
        expected=json.loads((TASK/'configs/SOURCE_ARCHIVE_IDENTITY.json').read_text())
        if provenance!=expected['official_archive']:raise RuntimeError('Official archive provenance changed')
        original=root/expected['original_extension']['filename']
        if sha(original)!=expected['original_extension']['sha256']:raise RuntimeError('Installed original extension changed')
        commit=provenance['commit']
    if commit!=lock['commit']:raise RuntimeError('Frozen DROID-W commit changed')
    for record in lock['files']:
        if not (root/record['path']).is_file() or sha(root/record['path'])!=record['sha256']:raise RuntimeError('Frozen DROID-W Python/config source changed')
    return root

def verify_candidate_identity():
    x=json.loads((TASK/'configs/NATIVE_EXTENSION_IDENTITY.json').read_text())
    root=Path(os.environ.get('TASK011B_NATIVE_ROOT','/root/rivermind-data/GAMECAM_TASK011B_20261127_AMP_NATIVE_R2'))
    p=root/'build_001/task011b_cadp_dr_c3414af6.so'
    if not p.is_file() or p.stat().st_size!=x['bytes'] or sha(p)!=x['sha256']:raise RuntimeError('Frozen candidate extension identity mismatch')
    return p

def load_candidate():
    p=verify_candidate_identity();name='task011b_cadp_dr_c3414af6'
    spec=importlib.util.spec_from_file_location(name,p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
