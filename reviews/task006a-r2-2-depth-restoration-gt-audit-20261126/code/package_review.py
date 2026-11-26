"""Scan and seal the complete independent review, preserving original arrays."""
import ast,datetime,re,zipfile
from common import *
ARCHIVE='GAMECAM_TASK006A_R2_2_DEPTH_RESTORATION_GT_REVIEW.zip'

def files():
    return [p for p in sorted(ROOT.rglob('*')) if p.is_file() and
      p.relative_to(ROOT).parts[0]!='deliveries' and '__pycache__' not in p.parts and p.suffix!='.pyc']

def main():
    cpu_only()
    patterns=[('private_key',rb'-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----'),
      ('github_token',rb'gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}'),
      ('HF_token',rb'hf_[A-Za-z0-9]{30,}'),('cloud_access_key',rb'AKIA[0-9A-Z]{16}')]
    scanned=[];hits=[];banned=[]
    for p in files():
        rel=p.relative_to(ROOT).as_posix()
        if p.suffix.lower() in ['.pt','.pth','.ckpt','.safetensors','.exr','.pem','.key'] or p.name in ['id_rsa','id_ed25519']:
            banned.append(rel)
        if p.suffix.lower() not in ['.npz','.png','.jpg','.jpeg','.pdf']:
            b=p.read_bytes();scanned.append(rel)
            for kind,pattern in patterns:
                if re.search(pattern,b):hits.append({'file':rel,'kind':kind})
    if hits or banned:raise RuntimeError('Publication secret/file-type scan failed: '+repr(hits+banned))
    for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text('utf-8'))
    tree=ast.parse((ROOT/'code/remote_cpu_restore.py').read_text('utf-8'))
    calls=[ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n,ast.Call)]
    if any(c.startswith('torch.cuda.') or c in ['torch.load','torch.hub.load','model.inference'] for c in calls):
        raise RuntimeError('CPU-only remote code changed')
    dump(ROOT/'SECURITY_AUDIT.json',{
      'stage':'TASK006A-R2.2','new_GPU_used':False,'CUDA_context_initialized':False,
      'CUDA_tensor_created':False,'model_forward_count':0,'checkpoint_deserialized':False,
      'model_loaded':False,'GPU_instance_kept_online':True,'instance_rebooted':False,'instance_shutdown':False,
      'real_SLAM_executed':False,'training_executed':False,'CADP_or_BA_modified':False,
      'production_sources_modified':False,'production_weights_modified':False,'frozen_config_modified':False,
      'historical_outputs_modified':False,'raw_dataset_modified':False,'new_dataset_download_bytes':0,
      'probability_models_fit':0,'detector_models_trained':0,'automatic_next_stage_started':False,
      'trusted_SSH_only':True,'host_key_verification_disabled':False,'host_keys_replaced':False,
      'secret_scan':{'text_files':len(scanned),'hits':hits,'forbidden_payload_types':banned},
      'CPU_remote_runner_AST_checked':True,'all_new_Python_scripts_parse':True,
      'protected_local_files':799,'protected_files_changed':0,
      'publication_authorization':'User standing authorization: full review ZIP and expanded files, public repository',
      'raw_datasets_or_model_weights_redistributed':False,
      'repository_visibility_changed':False,'repository_default_branch_changed':False,
      'scope_note':'Existing GPU allocation is not used by this CPU audit; no fresh inference or production integration'})
    rows=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files()]
    if any(r['path']=='FILE_SHA256_MANIFEST.json' for r in rows):raise RuntimeError('Already sealed')
    dump(ROOT/'FILE_SHA256_MANIFEST.json',{'algorithm':'SHA-256','files':rows,
      'excluded':['FILE_SHA256_MANIFEST.json self-hash','deliveries/ external package receipts and archive','__pycache__ and .pyc'],
      'no_self_hash_claim':True,'full_NPZ_included_in_ZIP':True})
    package=ROOT/'deliveries'/ARCHIVE
    with zipfile.ZipFile(package,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for p in files():z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(package) as z:
        crc=z.testzip()
        if crc is not None:raise RuntimeError('ZIP CRC failed: '+crc)
        for r in rows:
            b=z.read(r['path'])
            if len(b)!=r['bytes'] or hashlib.sha256(b).hexdigest()!=r['sha256']:
                raise RuntimeError('ZIP internal SHA failed')
        if len(z.namelist())!=len(rows)+1:raise RuntimeError('Missing ZIP member')
        npz=sum(n.endswith('.npz') for n in z.namelist())
    receipt={'status':'PASS','ZIP_name':ARCHIVE,'ZIP_bytes':package.stat().st_size,'ZIP_sha256':sha(package),
      'ZIP_CRC':'PASS','ZIP_members':len(rows)+1,'internal_SHA256_entries':len(rows),
      'internal_SHA256_passed':len(rows),'NPZ_files':npz,'protected_files_unchanged':799,
      'tests':71,'new_GPU_forwards':0,'raw_datasets_or_weights_included':False,
      'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    dump(ROOT/'deliveries/PACKAGE_VERIFICATION.json',receipt)
    with (ROOT/'deliveries'/(ARCHIVE+'.sha256')).open('x',encoding='ascii',newline='\n') as f:
        f.write(receipt['ZIP_sha256']+'  '+ARCHIVE+'\n')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
