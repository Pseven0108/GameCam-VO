"""Audit the newly acquired complete sequence; geometry is not a meter certificate."""
import csv,hashlib,json,os,pathlib,sys
import numpy as np
from PIL import Image
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT.parent/'task006a-r2-depth-prior-reliability-20261126/experiments/runtime_site'))
import OpenEXR
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def depth(p):return OpenEXR.File(str(p),separate_channels=True).channels()['Y'].pixels.astype(np.float64)
def camera(p):
 d=json.loads(p.read_text());return np.array([[d['f_x'],0,d['c_x']],[0,d['f_y'],d['c_y']],[0,0,1.]]),np.asarray(d['extrinsic'],float)
def project(seq,s,t,kind):
 ds=depth(seq/'depths'/f'{s:04d}.exr');dt=depth(seq/'depths'/f'{t:04d}.exr')
 ks,es=camera(seq/'poses'/f'{s:04d}.json');kt,et=camera(seq/'poses'/f'{t:04d}.json');T=et@np.linalg.inv(es)
 yy,xx=np.mgrid[4:ds.shape[0]-4:8,4:ds.shape[1]-4:8];z=ds[yy,xx];valid=np.isfinite(z)&(z>0)
 ray=np.linalg.solve(ks,np.vstack([xx[valid],yy[valid],np.ones(valid.sum())]))
 if kind=='range':ray/=np.linalg.norm(ray,axis=0)
 xyz=T[:3,:3]@(ray*z[valid])+T[:3,3,None];q=kt@xyz;u=q[0]/q[2];v=q[1]/q[2]
 keep=np.isfinite(u)&np.isfinite(v)&(xyz[2]>0)&(u>=0)&(u<dt.shape[1]-1)&(v>=0)&(v<dt.shape[0]-1)
 obs=dt[np.rint(v[keep]).astype(int),np.rint(u[keep]).astype(int)]
 pred=xyz[2,keep] if kind=='z' else np.linalg.norm(xyz[:,keep],axis=0)
 positive=np.isfinite(obs)&(obs>0);error=np.abs(pred[positive]-obs[positive])/obs[positive]
 return {'source':s,'target':t,'hypothesis':kind,'translation_native_units':float(np.linalg.norm(T[:3,3])),
  'rotation_distance_to_identity':float(np.linalg.norm(T[:3,:3]-np.eye(3))),'valid_points':len(error),
  'median_relative_depth_disagreement':float(np.median(error)),'P90':float(np.percentile(error,90)),
  'fraction_below_1pct':float((error<.01).mean()),'physical_units_proven':False}
def main():
 assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
 seq=ROOT/'inputs/MVS-Synth/GTAV_540/0001';rows=[];source=[]
 for i in range(100):
  stem=f'{i:04d}';rgb=seq/'images'/(stem+'.png');gt=seq/'depths'/(stem+'.exr');pose=seq/'poses'/(stem+'.json')
  with Image.open(rgb) as im:im.load();size=im.size;mode=im.mode
  d=depth(gt);k,e=camera(pose)
  if d.shape!=size[::-1] or mode!='RGB' or size!=(960,540):raise RuntimeError('RGB/GT shape mismatch')
  valid=np.isfinite(d)&(d>0)
  rows.append({'sequence':'0001','frame':stem,'width':size[0],'height':size[1],'valid_depth':int(valid.sum()),
   'Inf':int(np.isinf(d).sum()),'NaN':int(np.isnan(d).sum()),'nonpositive':int((d<=0).sum()),
   'GT_median_native_units':float(np.median(d[valid])),'fx':float(k[0,0]),'extrinsic_det':float(np.linalg.det(e[:3,:3])),
   'physical_depth_unit':'UNKNOWN_NATIVE_UNIT','rgb_sha256':sha(rgb),'GT_sha256':sha(gt),'pose_sha256':sha(pose)})
  for p in [rgb,gt,pose]:source.append({'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)})
 with (ROOT/'03_gt_admission/SECOND_SEQUENCE_FULL_AUDIT.csv').open('x',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
 comparisons=[project(seq,s,t,kind) for s,t in [(0,1),(49,50),(98,99)] for kind in ['z','range']]
 with (ROOT/'03_gt_admission/SECOND_SEQUENCE_PROJECTION.csv').open('x',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,list(comparisons[0]));w.writeheader();w.writerows(comparisons)
 old=ROOT.parents[1]/'data/mvs_synth/GTAV_540/0000/images'
 overlap=set(sha(p) for p in old.glob('*.png'))&set(r['rgb_sha256'] for r in rows)
 result={'sequence':'0001','RGB':100,'GT_depth':100,'camera':100,'all_decoded':True,
         'valid_GT_pixels':sum(x['valid_depth'] for x in rows),'Inf_sky':sum(x['Inf'] for x in rows),'NaN':sum(x['NaN'] for x in rows),
         'cross_sequence_RGB_exact_duplicate_hashes':len(overlap),'sequence_level_distinct_IDs':True,
         'recording_session_independence':'UNKNOWN','physical_camera_independence':'UNKNOWN',
         'physical_metric_unit':'NOT_ESTABLISHED','meter_accuracy_admitted':False,
         'secondary_calibration_only_native_unit_analysis_permitted':True,'raw_files':source,
         'official_complete_target_crosscheck':False,'official_stream_verified_subset':5,
         'author_issue25_unit_question_unanswered':True}
 with (ROOT/'03_gt_admission/GT_ADMISSION_FINAL.json').open('x',encoding='utf-8') as f:f.write(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k!='raw_files'},indent=2))
if __name__=='__main__':main()
