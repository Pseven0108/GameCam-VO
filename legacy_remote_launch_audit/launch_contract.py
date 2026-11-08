"""Frozen inputs and authorization gate. This module is stdlib-only and never deserializes weights."""
import csv,hashlib,io,json,os,pathlib,struct,sys
ROOT=pathlib.Path('/root/rivermind-data/gamecam/GameCam-VO')
AUDIT=pathlib.Path(__file__).resolve().parent.parent
PREFLIGHT=ROOT.parent/'setup/gpu_preflight_20261108'
REFERENCE=ROOT/'GameCam-WW-V5_7-NA-K6-A-GPU-R1'
FUTURE_ROOT=ROOT/'GameCam-WW-V5_7-NA-K6-A-GPU-R2'
ORIGINAL_SHA='a479e3d8e891f9cb323b9a337143409d460420854350ac8e023782b990ccd775'
PREPARED_SHA='70b2527e0293d695c77cdbca1ee4045d75b6483ff262fadd6b0da3749b68cfe9'
PIN_SPEC_SHA='11e2172ad1c9fe4ff7116381a264c7f4fcf9535db9352d320140748d9a92be33'
def sha(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb') as f:
        for x in iter(lambda:f.read(8*1024*1024),b''):h.update(x)
    return h.hexdigest()
def load(p):return json.loads(pathlib.Path(p).read_text(encoding='utf-8-sig'))
def mapped(p):return ROOT/pathlib.PurePosixPath(p).relative_to('/mnt/d/aaa/GameCam-VO')
def frozen_artifacts():
    spec_path=REFERENCE/'config/dependency_pins.json';assert sha(spec_path)==PIN_SPEC_SHA,'Dependency spec SHA drift'
    spec=load(spec_path)
    for r in spec['files'].values():assert sha(REFERENCE/r['path'])==r['sha256'] and (REFERENCE/r['path']).stat().st_size==r['bytes'],'Frozen metadata drift: '+r['path']
    original_path=mapped(spec['config']['path_linux']);prepared_path=PREFLIGHT/'GPU_09_120frame_effective_config.json'
    assert sha(original_path)==ORIGINAL_SHA and sha(prepared_path)==PREPARED_SHA,'Frozen config SHA drift'
    original=load(original_path);cfg=load(prepared_path);diff=[]
    def walk(a,b,path=''):
        if isinstance(a,dict) and isinstance(b,dict):
            assert set(a)==set(b),'Config keys differ'
            for k in a:walk(a[k],b[k],path+'.'+k if path else k)
        elif a!=b or type(a) is not type(b):diff.append({'field':path,'original':a,'prepared':b})
    walk(original,cfg);assert {x['field'] for x in diff}=={'max_frames','data.output'} and len(diff)==2
    assert cfg['max_frames']==120 and cfg['stride']==1 and cfg['tracking']['buffer']==350 and cfg['tracking']['warmup']==12
    assert cfg['tracking']['motion_filter']['thresh']==3. and cfg['mapping']['enable'] is False and cfg['dataset']=='youtube' and cfg['debug'] is False
    assert cfg['data']['output']==str(FUTURE_ROOT/'runs/droidw/V56_01_middle')
    assert pathlib.Path('/mnt/d/aaa/GameCam-VO').resolve()==ROOT
    cases=load(REFERENCE/'config/cases.json');assert len(cases)==1;case=cases[0]
    assert case['case_id']=='V56_01_middle' and case['frame_start']==7953 and case['max_test_frame']==8072 and len(case['frames'])==120
    rows=list(csv.DictReader(io.StringIO((REFERENCE/'config/k4_input_frames.csv').read_text(encoding='utf-8-sig'))));assert len(rows)==120
    k4_path=mapped(spec['k4_live_contract']['path_linux']);assert sha(k4_path)==spec['k4_live_contract']['sha256'];k4=load(k4_path)
    K=k4['K_input'];assert K==case['K_input'] and k4['resolution']==[512,288]
    expected=[375.1328252,375.1328252,255.7,143.7];assert [cfg['cam'][k] for k in ['fx','fy','cx','cy']]==expected==case['K4']
    input_checks=[]
    for i,(r,f) in enumerate(zip(rows,case['frames'])):
        p=mapped(f['path_linux']);raw=p.read_bytes();h=hashlib.sha256(raw).hexdigest()
        assert raw[:8]==b'\x89PNG\r\n\x1a\n' and raw[12:16]==b'IHDR' and struct.unpack('>II',raw[16:24])==(512,288),'PNG header contract mismatch'
        ok=f['ordinal']==int(r['ordinal'])==i and f['frame']==int(r['published_frame_index'])==7953+i and int(p.stem.removeprefix('frame'))==7953+i and h==r['png_sha256']==f['png_sha256']==r['expected_png_sha256'] and p.stat().st_size==int(r['bytes']) and p.resolve()==pathlib.Path(f['path_linux']).resolve()
        ok=ok and [float(r[k]) for k in ['fx','fy','cx','cy']]==expected and r['all_pass']=='True'
        assert ok,'Input integrity failure: '+str(i)
        input_checks.append({'ordinal':i,'published_frame':7953+i,'path':str(p),'realpath':str(p.resolve()),'bytes':len(raw),'sha256':h,'PNG_IHDR':[512,288],'K':expected,'passed':ok})
    weights=[]
    for w in spec['weights']:
        p=mapped(w['path_linux']);expected_real=mapped(w['real_linux']);h=sha(p)
        ok=h==w['sha256'] and p.stat().st_size==w['bytes'] and p.resolve()==expected_real.resolve()
        assert ok,'Checkpoint integrity failure: '+w['id']
        weights.append({'id':w['id'],'path':str(p),'requested_logical_path':w['path_linux'],'realpath':str(p.resolve()),'expected_sha256':w['sha256'],'sha256':h,'bytes':p.stat().st_size,'passed':ok})
    return {'input':{'checks':input_checks,'frames':120,'published_start':7953,'published_end':8072,'full_window_end':8252,'input_realpath':str(pathlib.Path(cfg['data']['input_folder']).resolve()),'input_folder':cfg['data']['input_folder'],'K_input':K,'RGB_decoded':False,'raw_bytes_hashed':True,'GT_values_read':False,'passed':all(x['passed'] for x in input_checks)},'weights':{'weights':weights,'weights_checked':len(weights),'checkpoint_deserialized':False,'passed':len(weights)==4 and all(x['passed'] for x in weights)},'config':{'original_path':str(original_path),'original_sha256':ORIGINAL_SHA,'prepared_path':str(prepared_path),'prepared_sha256':PREPARED_SHA,'differences':diff,'save_gt_poses':cfg['save_gt_poses'],'dataset_dispatch':'youtube -> RGB_NoPose','GT_isolation_requires_selected_loader_and_bounded_adapter':True,'config_modified':False,'future_output':cfg['data']['output'],'future_output_created':False,'passed':True},'cfg':cfg,'case':case,'spec':spec}

def validate_candidate(path):
    candidate=load(path)
    assert candidate['model_execution_authorized'] is False and candidate['model_attempt_limit']==0 and candidate['model_attempts']==0
    target=candidate['future_target'];assert target=={'method':'droidw','case':'V56_01_middle','start_published_frame':7953,'max_frames':120,'stride':1,'mapping':False,'buffer':350,'warmup':12,'motion_filter':3.0,'maximum_authorizable_attempts':1,'automatic_retry':False}
    for r in candidate['frozen_runtime_files']:assert sha(AUDIT/r['path'])==r['sha256'],'Runner source SHA changed: '+r['path']
    for name,h in candidate['passed_report_pins'].items():assert sha(AUDIT/name)==h and load(AUDIT/name)['passed'],'Readiness report pin failed: '+name
    return candidate

def require_authorization(candidate_path,authorization_path):
    if not authorization_path:raise RuntimeError('MODEL_EXECUTION_NOT_AUTHORIZED:NO_AUTHORIZATION_FILE')
    candidate=validate_candidate(candidate_path);auth=load(authorization_path)
    if not (auth.get('model_execution_authorized') is True and auth.get('model_attempt_limit')==1 and auth.get('authorized_launch_contract_sha256')==sha(candidate_path) and auth.get('method')=='droidw' and auth.get('case')=='V56_01_middle' and auth.get('max_frames')==120 and auth.get('automatic_retry') is False):raise RuntimeError('MODEL_EXECUTION_NOT_AUTHORIZED:AUTHORIZATION_CONTRACT_MISMATCH')
    return candidate,auth

def claim_once(path,record):
    with pathlib.Path(path).open('x') as f:json.dump(record,f,indent=2)