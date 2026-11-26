"""Read-only TASK007D source/history/metadata checks; no model dependencies.

Run with the existing gamecam-vo Python and CUDA_VISIBLE_DEVICES=-1.
sources_work contains local research captures, never public raw data or models.
"""
import csv
from collections import Counter
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import sys
import tarfile

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT.parents[1]
WORK=ROOT/'sources_work'
UIDS=['016d3596da27','03b9161e3ff2','0caf78b8eeac']
REV='4e34897a2fcf8e1cc44b1ae8d2bbd0188c8f2841'
HEAD='bd91509e0b840f3082848cd561da60a695e6b70b'


def sha(b):return hashlib.sha256(b).hexdigest()
def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def read(name):return json.loads((ROOT/name).read_text('utf-8'))
def dump(name,data):
    p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def csvout(name,rows):
    p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
def parse_history(name):
    raw=(WORK/name).read_text('utf-8')
    for hit in re.finditer(r'data-props="([^"]+)"',raw):
        try:d=json.loads(html.unescape(hit[1]))
        except (ValueError,TypeError):continue
        if isinstance(d,dict) and isinstance(d.get('commits'),list):return d['commits']
    raise ValueError('Official file-specific commit history absent; do not guess')


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='-1' and 'torch' not in sys.modules
    cap=read('sources_work/CONNECTOR_CAPTURE.json')
    assert cap['checked_head']==HEAD and len(cap['commits'])==26
    commits=cap['commits'];ids={c['sha'] for c in commits}
    assert all(p in ids for c in commits for p in c['parents'])
    assert sum(not c['parents'] for c in commits)==1
    assert cap['tree']['truncated'] is False and cap['branches'][0]['commit']['sha']==HEAD
    history=[{'sha':c['sha'],'date_UTC':c['date'],'subject':c['message'].split('\n')[0],
              'parents':c['parents'],'url':c['url'],'changed_files':[{k:f.get(k) for k in ['filename','previous_filename','status','sha']} for f in c['files']]} for c in commits]
    dump('evidence/GITHUB_COMMIT_HISTORY.json',{'head':HEAD,'commits':history,'parents_closed_to_root':True,
         'coverage':'26 reachable commits plus separately checked empty page2; one main branch. No claim about private/unreachable history'})
    dump('evidence/GITHUB_TREE.json',cap['tree'])
    # All historical source changes, including the pre-scale implementations.
    patches=[{'commit':c['sha'],'date_UTC':c['date'],'url':c['url'],'files':[f for f in c['files'] if f['filename'].startswith('scripts/')]} for c in commits]
    dump('sources/GITHUB_CODE_HISTORY_PATCHES.json',[c for c in patches if c['files']])
    files=[]
    for path in ['README.md','scripts/utils.py']:
        old=PROJECT/'reviews/task007c-omniworld-metric-gt-admission-overlap-20261126/sources/omniworld'
        src=old/('GITHUB_README.md' if path=='README.md' else 'utils.py')
        b=src.read_bytes();expect=next(x['sha'] for x in cap['tree']['tree'] if x['path']==path)
        assert blob(b)==expect
        out=ROOT/'sources/official'/path;out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('xb') as f:f.write(b)
        files.append({'path':out.relative_to(ROOT).as_posix(),'git_blob':expect,'sha256':sha(b),'bytes':len(b),
                      'url':f'https://github.com/yangzhou24/OmniWorld/blob/{HEAD}/{path}'})
    extra=read('sources_work/EXTRA_SOURCE_CAPTURE.json')
    for entry in extra['files']:
        b=entry['content'].encode('utf-8')
        assert blob(b)==entry['blob_sha']
        out=ROOT/'sources/official'/entry['path'];out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('xb') as f:f.write(b)
        files.append({'path':out.relative_to(ROOT).as_posix(),'git_blob':entry['blob_sha'],'sha256':sha(b),'bytes':len(b),'url':entry['source_url']})
    assert len(files)==6
    dump('evidence/SOURCE_BLOB_VERIFICATION.json',{'all_current_text_code_files':files,'status':'6/6 PASS',
         'all_reachable_script_patch_versions_recorded':True,'source_executed':False})

    mh=parse_history('HF_METADATA_HISTORY.html');rh=parse_history('HF_README_HISTORY.html')
    assert len(mh)==6 and mh[0]['commit']['id']=='a3934526f95d4e6be043868a08ee4cdac4eacfee'
    clean=lambda x:{'id':x['commit']['id'],'parents':x['commit']['parentIds'],'date_UTC':x['date'],'subject':x['title'],
                   'authors':[a['user'] for a in x['authors']]}
    dump('evidence/HF_FILE_SPECIFIC_HISTORY.json',{'metadata':list(map(clean,mh)),'README':list(map(clean,rh)),
         'metadata_history_url':'https://huggingface.co/datasets/InternRobotics/OmniWorld/commits/main/metadata/omniworld_game_metadata.csv',
         'scope':'File-specific official HTML structured history, not the unrelated100 most recent dataset uploads'})
    versions=[];target_history=[]
    for c in reversed(mh):
        date=c['date'][:10].replace('-','');p=WORK/('metadata_'+date+'.csv')
        b=p.read_bytes();receipt=json.loads(p.with_name(p.name+'.receipt.json').read_text('utf-8'))
        assert sha(b)==receipt['sha256'] and len(b)==receipt['bytes']
        rows=list(csv.DictReader(b.decode('utf-8-sig').splitlines()));header=list(rows[0]);scale='Metric Scale' in header
        assert len({x['UID'] for x in rows})==len(rows)
        if scale:assert all(math.isfinite(float(x['Metric Scale'])) and float(x['Metric Scale'])>0 for x in rows)
        versions.append({'commit':c['commit']['id'],'date_UTC':c['date'],'rows':len(rows),'headers':header,
                         'Metric_Scale_column':scale,'bytes':len(b),'sha256':sha(b),'git_blob':blob(b),'source_url':receipt['url']})
        for uid in UIDS:
            hits=[x for x in rows if x['UID']==uid]
            target_history.append({'commit':c['commit']['id'],'date_UTC':c['date'],'uid':uid,'row_present':bool(hits),
                                   'scale_column_present':scale,'Metric_Scale_original_string':hits[0].get('Metric Scale','') if hits else '',
                                   'test_split_indices':hits[0].get('Test Split Index','') if hits else ''})
    csvout('evidence/UID_SCALE_HISTORY.csv',target_history)
    current=list(csv.DictReader((WORK/'metadata_20260321.csv').read_text('utf-8-sig').splitlines()))
    prior=list(csv.DictReader((WORK/'metadata_pre_release_parent.csv').read_text('utf-8-sig').splitlines()))
    cm={r['UID']:r for r in current};pm={r['UID']:r for r in prior}
    assert set(cm)==set(pm) and len(cm)==484
    assert all({k:v for k,v in cm[uid].items() if k!='Metric Scale'}==pm[uid] for uid in cm)
    new_bytes=(WORK/'metadata_20260321.csv').read_bytes()
    local=PROJECT/'GAMECAM_OWG_PREFLIGHT_20261115/evidence/omniworld_game_metadata.csv'
    before=local.read_bytes();assert before==new_bytes
    mt=json.loads((WORK/'HF_METADATA_TREE.json').read_text('utf-8'))
    latest=next(x for x in mt if x['path']=='metadata/omniworld_game_metadata.csv')
    assert blob(before)==latest['oid']=='00b580ead4422f315800191127cf749b38eff697'
    dump('evidence/HF_METADATA_VERSION_AUDIT.json',{'versions':versions,'scale_first_in_checked_path_history':'2026-03-21T09:17:44.000Z',
         'new_column_only_vs_direct_parent':True,'unchanged_non_scale_rows':484,'all_484_factors_finite_positive':True,
         'release_csv_equals_existing_local_and_current_HF_blob':True,'current_HF_revision':REV,
         'scope':'First publication of fields verified; calculation time, generating model or method not inferred'})
    csvout('UID_SCALE_AUDIT.csv',[{'uid':uid,'factor_original_string':cm[uid]['Metric Scale'],
          'first_scale_commit':'a3934526f95d4e6be043868a08ee4cdac4eacfee','first_scale_published_UTC':'2026-03-21T09:17:44.000Z',
          'current_source_revision':REV,'CSV_row_unique':True,'current_equals_release':True,
          'consumer_depth':'valid decoded depth multiplied by factor','consumer_pose':'camera-to-world translation multiplied by same factor',
          'generator_code_or_run_receipt':'NOT_FOUND_IN_INSPECTED_SOURCES','generator_same_for_three_UIDs':'UNVERIFIED',
          'MoGe2_used_for_actual_factor':'UNVERIFIED','Metric3D_used_for_actual_factor':'UNVERIFIED',
          'independent_physical_anchor':'NOT_ESTABLISHED','physical_error_interval':'UNAVAILABLE',
          'official_test_split_indices':cm[uid]['Test Split Index'],'factor_fit_frames_or_splits':'UNPUBLISHED',
          'strict_metric_GT_admission':'NO_GO','usage_class':'B_RELATIVE_OR_AUXILIARY_ONLY_WITH_LIMITS'} for uid in UIDS])

    descriptions={3322227112:'Author says the pre-release Game depth was not metric and point-map training used normalization.',
      3326289730:'Author says depth and camera translations share a scale; no physical-length anchor is supplied.',
      3404344533:'Optional far-depth filtering is suggested for training stability, not for physical calibration.',
      3494867729:'Author explains ReShade buffer linearization and says division by0.004 is numerical scaling for stability.',
      3566565501:'Author says pre-release extrinsics were nonmetric but on the same scale as depth.',
      3568742850:'Author distinguishes directly captured ReShade Game depth from model-annotated DROID/HOI4D subdatasets.',
      3570627221:'Author suggests a scene median-ratio scale from MoGe-2 metric predictions on sampled frames as a practical approximation; does not identify the later released CSV factors.',
      3473099994:'Author says the acquisition pipeline was custom to their research environment; no public collector implementation is provided in the reply.',
      4127257933:'Author directs users to the released metadata CSV; the reply supplies location, not the generation recipe.',
      5384909434:'Author says Game cameras were estimated with DroidCalib/DROID-SLAM plus refinement, not exported engine cameras; this is not an independent metric motion measurement.'}
    owner=[]
    for c in cap['comments']:
        if c['id'] not in descriptions:continue
        assert c['association']=='OWNER' and c['author']=='yangzhou24'
        owner.append({k:c[k] for k in ['issue','id','url','author','association','date','updated']}|
                     {'body_sha256':sha(c['body'].encode('utf-8')),'interpretation':descriptions[c['id']],
                      'evidence_type':'Author explanation, not a released per-UID factor-generation run log'})
    assert len(owner)==len(descriptions)
    dump('evidence/AUTHOR_STATEMENTS.json',{'records':owner,'full_bodies_not_republished':True,
         'chronology_warning':'2025 suggestions precede March2026 factor release; no assertion that the suggestion was used to produce the current CSV'})
    dump('evidence/DISCUSSION_COVERAGE.json',{'GitHub_issue_or_PR_entries_listed':len(cap['issues']),'entries':cap['issues'],
         'comment_threads_read':[3,6,10,19,20,23],'comments_read':len(cap['comments']),
         'other_threads':'Titles/body screening only; not every unrelated thread comment was retrieved',
         'HF_public_discussions_listed':[{k:c[k] for k in ['num','title','status','createdAt','isPullRequest']} for c in read('sources_work/HF_DISCUSSIONS.json')['discussions']],
         'HF_discussion_count':2,'HF_relevance':'Visible entries concern a README rename PR and bot conversion, not scale provenance; neither was executed',
         'scope':'No contact with authors; no universal claim about all public/private correspondence'})

    intake=json.loads((PROJECT/'reviews/task007c-omniworld-metric-gt-admission-overlap-20261126/evidence/CANDIDATE_INTAKE.json').read_text('utf-8'))['candidates']
    archive_checks=[]
    for c in intake:
        p=Path(c['others_archive']['path']);b=p.read_bytes()
        assert sha(b)==c['others_archive']['sha256']
        with tarfile.open(p,'r:gz') as z:
            members=[m for m in z.getmembers() if m.isfile()]
            readable=[m for m in members if m.name.lower().endswith(('.yaml','.yml','.cfg','.ini','.py','.sh','.txt','.md','.log'))]
            candidates=[m for m in members if re.search('moge|metric|scale|config|calib|log',m.name,re.I)]
            archive_checks.append({'uid':c['uid'],'archive_sha256':sha(b),'archive_bytes':len(b),'regular_member_count':len(members),
              'extension_counts':dict(Counter(Path(m.name).suffix.lower() for m in members)),
              'readable_recipe_or_log_files':[{'path':m.name,'bytes':m.size} for m in readable],
              'provenance_keyword_filename_hits':[{'path':m.name,'bytes':m.size} for m in candidates],
              'binary_arrays_or_pickles_deserialized':False,
              'scope':'Header/name/type audit plus existing metadata; unparsed binary contents not certified free of hidden metadata'})
    dump('evidence/LOCAL_OTHERS_PROVENANCE_SEARCH.json',archive_checks)
    preservation=[]
    for slug in ['task007a-mpsfm-confidence-calibration-audit-20261126','task007b-depth-gt-availability-alternative-data-audit-20261126',
                 'task007c-omniworld-metric-gt-admission-overlap-20261126']:
        p=PROJECT/'reviews'/slug
        mf=(p/'FILE_SHA256_MANIFEST.json').read_bytes();rows=json.loads(mf)['files']
        for row in rows:
            data=(p/row['path']).read_bytes()
            assert len(data)==row['bytes'] and sha(data)==row['sha256']
        preservation.append({'review':slug,'manifest_sha256':sha(mf),'manifest_entries_verified':len(rows),'status':'PASS'})
    assert local.read_bytes()==before
    dump('evidence/HISTORICAL_PRESERVATION.json',{'sealed_review_manifests':preservation,'metadata_sha256_before_after':sha(before),
         'local_others':archive_checks,'old_files_written':0,'historical_Releases_modified':False,
         'scope':'Read-back against sealed manifests and reused inputs; not an exhaustive hash of every project asset'})

    # Mathematical non-identifiability demonstration, not a model/GT experiment.
    K=np.array([[600.,0,640.],[0,600.,360.],[0,0,1.]])
    points=np.array([[-1.,.2,3.],[0.,-.1,7.],[3.,2.,20.],[4.,1.,50.]])
    angle=.17;R=np.array([[np.cos(angle),0,np.sin(angle)],[0,1,0],[-np.sin(angle),0,np.cos(angle)]])
    t=np.array([.4,-.1,.2])
    project=lambda x:(K@x.T).T[:,:2]/(K@x.T).T[:,2,None]
    p0=project(points@R.T+t)
    scales=[.1,2.,10.,207.00688933270382];errs=[]
    for s in scales:
        err=float(np.max(np.abs(project((s*points)@R.T+s*t)-p0)));assert err<1e-10
        errs.append({'arbitrary_global_scale':s,'max_reprojection_pixel_difference':err})
    x=np.array([.02,.2,.5,.9]);c=.004;s=207.00688933270382;c2=.008;s2=s*c2/c
    f=lambda x:x/(1000.-999.*x)
    residual=float(np.max(np.abs(s*f(x)/c-s2*f(x)/c2)));assert residual<1e-12
    dump('evidence/SCALE_IDENTIFIABILITY_DEMONSTRATION.json',{'type':'Synthetic float64 mathematics only, no real depth/pose inference',
         'shared_depth_translation_scaling':errs,'division_factor_reparameterization':{'old_divisor':c,'new_divisor':c2,'old_scene_scale':s,'new_scene_scale':s2,'output_difference':residual},
         'implication':'Reprojection consistency and application of a scalar do not determine its physical unit; an independent unit anchor is needed',
         'real_metric_accuracy_test':False})
    receipts=[]
    for p in WORK.glob('*.receipt.json'):
        r=json.loads(p.read_text('utf-8'));data=p.with_name(p.name[:-len('.receipt.json')]).read_bytes()
        assert sha(data)==r['sha256'] and len(data)==r['bytes']
        receipts.append({'local_capture':p.name[:-len('.receipt.json')],**r})
    dump('evidence/PUBLIC_TEXT_FETCH_RECEIPTS.json',{'successful_resources':receipts,'bytes_read':sum(x['bytes'] for x in receipts),
         'connector_resources_accounted_separately':True,'failed_endpoints':'See ACCESS_LIMITATIONS.json','raw_RGB_depth_archives_or_models_downloaded':0})
    dump('evidence/AUDIT_VERIFICATION.json',{'source_text_blobs':'6/6 PASS','reachable_GitHub_commits':26,'GitHub_parent_chain_complete_to_root':True,
         'metadata_file_history_versions':6,'metadata_target_rows_audited':18,'unchanged_non_scale_rows_on_release':484,
         'positive_finite_released_factors':484,'selected_factors_match_release_and_current':True,'author_records_validated':len(owner),
         'historical_review_manifest_entries_verified':sum(x['manifest_entries_verified'] for x in preservation),
         'synthetic_projection_invariance_cases':4,'mathematical_scale_identified_from_these_checks':False,
         'model_runs':0,'GPU_CUDA_calls':0,'torch_imported':'torch' in sys.modules,'new_dependencies':0,
         'status':'EVIDENCE_AND_IDENTITIES_VERIFIED_NOT_METRIC_ACCURACY_PASS'})
    print(json.dumps(read('evidence/AUDIT_VERIFICATION.json'),indent=2))


if __name__=='__main__':main()
