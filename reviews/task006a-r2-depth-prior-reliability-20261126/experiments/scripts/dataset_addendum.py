"""Additional provenance/observability checks; preserve first audit outputs."""
import hashlib,json,pathlib,shutil
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[2];PROJECT=ROOT.parents[1]
def main():
 src=PROJECT/'docs/sources/mvs_synth'
 original=json.loads((src/'mirror_official_crosscheck.json').read_text(encoding='utf-8-sig'))
 tree=json.loads((src/'mirror_sequence_0000_tree.json').read_text(encoding='utf-8-sig'))
 checks=[]
 for row in tree:
  if row['type']!='file':continue
  p=PROJECT/'data/mvs_synth'/row['path'];b=p.read_bytes()
  expected=row.get('lfs',{}).get('oid')
  actual=hashlib.sha256(b).hexdigest() if expected else hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
  expected=expected or row['oid']
  checks.append({'path':str(p),'bytes':len(b),'matches':actual==expected,'expected':expected,'observed':actual})
 subset=[]
 for row in original['files']:
  p=PROJECT/'data/mvs_synth'/row['path'];b=p.read_bytes()
  actual=hashlib.sha256(b).hexdigest() if row['algorithm']=='sha256' else hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
  subset.append({'path':row['path'],'matches_historical_official_subset':actual==row['digest']})
 pairs=[]
 for s,t in [(0,1),(49,50),(98,99)]:
  def e(i):return np.array(json.loads((PROJECT/f'data/mvs_synth/GTAV_540/0000/poses/{i:04d}.json').read_text())['extrinsic'])
  rel=e(t)@np.linalg.inv(e(s));translation=np.linalg.norm(rel[:3,3]);rotation=np.linalg.norm(rel[:3,:3]-np.eye(3))
  pairs.append({'source':s,'target':t,'translation_native_units':float(translation),'rotation_matrix_distance':float(rotation),
   'has_nontrivial_baseline':bool(translation>1e-8 or rotation>1e-8),
   'may_discriminate_depth_z_vs_ray_range':bool(translation>1e-8)})
 for name in ['mirror_official_crosscheck.json','mirror_sequence_0000_tree.json','DeepMVS_README.md','generate_volume_train.py']:
  dst=ROOT/'evidence/MVS_PROVENANCE'/name;dst.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(src/name,dst)
 out={'mirror_repository':original['mirror'],'mirror_revision':original['mirror_revision'],
   'historical_official_revision':original['official_revision'],
   'mirror_files_reverified':len(checks),'mirror_matches':sum(x['matches'] for x in checks),
   'historical_official_subset_reverified':len(subset),'official_subset_matches':sum(x['matches_historical_official_subset'] for x in subset),
   'all_300_independently_matched_to_official_archive':False,
   'frame_pairs':pairs,'physical_unit_still_unknown':True,
   'note':'0->1 has negligible relative motion and cannot establish Z-vs-range convention; 49->50 and98->99 are the informative diagnostics',
   'mirror_checks':checks,'official_subset_checks':subset}
 path=ROOT/'03_dataset_audit/MVS_PROVENANCE_OBSERVABILITY_ADDENDUM.json'
 with path.open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2,allow_nan=False)
 if not all(x['matches'] for x in checks) or not all(x['matches_historical_official_subset'] for x in subset):raise ValueError('Existing data identity mismatch')
 print(json.dumps({k:v for k,v in out.items() if k not in ['mirror_checks','official_subset_checks']},indent=2))
if __name__=='__main__':main()
