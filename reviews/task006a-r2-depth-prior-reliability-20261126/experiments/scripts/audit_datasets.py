"""Read real local files, preserve hashes; no predicted GT or model execution."""
import csv,hashlib,json,os,sys,zipfile
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT.parents[1]
sys.path.insert(0,str(ROOT/'experiments/runtime_site'))
import OpenEXR
MVS=PROJECT/'data/mvs_synth/GTAV_540'


def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()

def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def table(p,rows):
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rows)

def depth(path):
 f=OpenEXR.File(str(path),separate_channels=True)
 if list(f.channels())!=['Y']:raise ValueError('Expected single Y channel')
 d=f.channels()['Y'].pixels
 if d.ndim!=2:raise ValueError('Depth shape')
 return d.copy()

def camera(path):
 c=json.loads(path.read_text());e=np.asarray(c['extrinsic'],float)
 k=np.array([[c['f_x'],0,c['c_x']],[0,c['f_y'],c['c_y']],[0,0,1.]])
 return k,e

def project_pair(seq,source_id,target_id,target_depth_override=None,kind='z'):
 ds=depth(seq/'depths'/f'{source_id:04d}.exr').astype(float)
 dt=depth(seq/'depths'/f'{target_depth_override if target_depth_override is not None else target_id:04d}.exr').astype(float)
 ks,es=camera(seq/'poses'/f'{source_id:04d}.json');kt,et=camera(seq/'poses'/f'{target_id:04d}.json')
 # Original documented W2C matrices; their reflections cancel in relative pose.
 transform=et@np.linalg.inv(es)
 yy,xx=np.mgrid[4:ds.shape[0]-4:8,4:ds.shape[1]-4:8]
 zz=ds[yy,xx];keep=np.isfinite(zz)&(zz>0)
 xx=xx[keep];yy=yy[keep];zz=zz[keep]
 rays=np.linalg.solve(ks,np.vstack([xx,yy,np.ones(len(xx))]))
 if kind=='range':rays=rays/np.linalg.norm(rays,axis=0)
 xyz=transform[:3,:3]@(rays*zz)+transform[:3,3,None]
 projected=kt@xyz;u=projected[0]/projected[2];v=projected[1]/projected[2]
 inside=np.isfinite(u)&np.isfinite(v)&(xyz[2]>0)&(u>=0)&(u<dt.shape[1]-1)&(v>=0)&(v<dt.shape[0]-1)
 u=np.rint(u[inside]).astype(int);v=np.rint(v[inside]).astype(int)
 predicted=xyz[2,inside] if kind=='z' else np.linalg.norm(xyz[:,inside],axis=0)
 observed=dt[v,u]
 valid=np.isfinite(observed)&(observed>0)
 rel=np.abs(predicted[valid]-observed[valid])/observed[valid]
 return {'source':source_id,'target':target_id,'target_depth_file':target_depth_override if target_depth_override is not None else target_id,
         'depth_convention_hypothesis':kind,'sample_grid_stride':8,'valid_points':len(rel),
         'median_relative_depth_disagreement':float(np.median(rel)),'P90_relative_depth_disagreement':float(np.percentile(rel,90)),
         'fraction_below_1pct':float(np.mean(rel<0.01)),
         'physical_clock_or_meter_accuracy_proven':False}

def main():
 if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise RuntimeError('CPU required')
 target=ROOT/'03_dataset_audit';dst=target/'R2_03_DATASET_MANIFEST.csv'
 if dst.exists():raise RuntimeError('Audit already sealed')
 rows=[];protected=[];seqs=[]
 for seq in sorted(p for p in MVS.iterdir() if p.is_dir()):
  rgb=list(sorted((seq/'images').glob('*.png')));gt=list((seq/'depths').glob('*.exr'));poses=list((seq/'poses').glob('*.json'))
  seqs.append({'sequence':seq.name,'rgb_count':len(rgb),'GT_EXR_count':len(gt),'pose_count':len(poses),
               'role':'AUDIT_ONLY_NOT_CALIBRATION_OR_INDEPENDENT_TEST'})
  for image in rgb:
   frame=image.stem;dp=seq/'depths'/(frame+'.exr');cp=seq/'poses'/(frame+'.json')
   if not dp.is_file() or not cp.is_file():raise ValueError('Missing modality')
   d=depth(dp);k,e=camera(cp)
   with Image.open(image) as im:
    im.load();size=im.size;mode=im.mode
   if d.shape!=(size[1],size[0]):raise ValueError('Unaligned shape')
   valid=np.isfinite(d)&(d>0);finite=d[valid].astype(float)
   row={'dataset':'MVS-Synth','sequence':seq.name,'frame_id':frame,'rgb_path':str(image),'depth_path':str(dp),'camera_path':str(cp),
        'width':size[0],'height':size[1],'RGB_mode':mode,'depth_dtype':str(d.dtype),'valid_depth_count':int(valid.sum()),
        'inf_count':int(np.isinf(d).sum()),'nan_count':int(np.isnan(d).sum()),'nonpositive_count':int((d<=0).sum()),
        'depth_min_native':float(finite.min()),'depth_median_native':float(np.median(finite)),'depth_P99_native':float(np.percentile(finite,99)),
        'K_fx':k[0,0],'K_fy':k[1,1],'extrinsic_det':float(np.linalg.det(e[:3,:3])),
        'metric_unit':'UNVERIFIED_NATIVE_GAME_UNIT','depth_GT_independent_of_R1':True,'metric_accuracy_admitted':False,
        'role':'AUDIT_ONLY_NO_CALIBRATION_OR_MODEL_SELECTION'}
   for label,p in [('rgb',image),('depth',dp),('camera',cp)]:
    h=sha(p);row[label+'_sha256']=h;protected.append({'path':str(p),'sha256':h,'bytes':p.stat().st_size})
   rows.append(row)
 table(dst,rows)
 comparisons=[]
 for a,b in [(0,1),(49,50),(98,99)]:
  for kind in ('z','range'):
   comparisons.append(project_pair(MVS/'0000',a,b,kind=kind))
  comparisons.append(project_pair(MVS/'0000',a,b,target_depth_override=50 if b!=50 else 99,kind='z'))
 table(target/'MVS_GT_MULTIVIEW_ALIGNMENT.csv',comparisons)
 archive_root=PROJECT/'downloads/VIPER_RGB_JPG_ORIGINALS_20261119/archives'
 archive_rows=[]
 for p in sorted(archive_root.glob('*.zip')):
  with zipfile.ZipFile(p) as z:
   members=z.infolist();suffixes={}
   for m in members:
    ext=Path(m.filename).suffix.lower();suffixes[ext]=suffixes.get(ext,0)+1
  archive_rows.append({'archive':str(p),'bytes':p.stat().st_size,'central_directory_members':len(members),
      'suffix_counts':json.dumps(suffixes),'dense_depth_payload_present':False,
      'scope':'Local RGB archives only; no claim that official VIPER has no other products'})
 table(target/'VIPER_LOCAL_ARCHIVE_MODALITIES.csv',archive_rows)
 camera_zip=PROJECT/'audits/VIPER_R0_1_TRAIN_AND_VO_PROTOCOL_AUDIT/02_metadata/train_camera.zip'
 with zipfile.ZipFile(camera_zip) as z:camera_names=z.namelist()
 preview=PROJECT/'data/mvs_synth/_dynamic_preview_audit/20261030T180848_750609Z_four_sequence_screening/manifest.json'
 preview_info=json.loads(preview.read_text(encoding='utf-8'))
 dump(target/'DATA_ADMISSION.json',{'MVS_local_sequences':seqs,'MVS_audited_frames':len(rows),
    'MVS_format':'Single-channel Y HALF EXR; +inf is documented sky, not replaced',
    'MVS_physical_unit_established':False,'MVS_metric_accuracy_admitted':False,
    'MVS_depth_GT_file_alignment':'Filename, dimensions and multiview diagnostics only; no independent sensor accuracy certificate',
    'MVS_independent_calibration_test_split_available':len(seqs)>=2,
    'MVS_preview_only_sequences':preview_info['sequences'],
    'MVS_preview_official_archive_identity_verified':False,
    'MVS_official_size_540':'9GB; full download not attempted',
    'MVS_official_license':'Research and educational use only',
    'VIPER_audited_RGB_archives':len(archive_rows),'VIPER_train_camera_archive':str(camera_zip),
    'VIPER_train_camera_members':len(camera_names),'VIPER_dense_depth_GT_found_in_audited_local_inputs':False,
    'new_dataset_download_bytes':0,'independent_error_validation_ready':False,
    'blocking_reasons':['No matched-unit independent depth GT for VIPER','MVS physical unit/convention admission incomplete',
                        'Only one complete local MVS sequence; no independent calibration/test split']})
 dump(ROOT/'evidence/DATA_PROTECTION_BEFORE.json',{'files':protected})
 contract={'figure':'MVS local GT audit','claim':'Real EXR depth and sky masks exist, but do not establish meter units or Metric3D reliability',
   'panels':['original RGB thumbnails','GT depth native units, LogNorm display only','finite-positive GT mask'],
   'archetype':'image plate + quant','backend':'Python/matplotlib','exports':['PNG','SVG'],
   'integrity':'Only display normalization; +inf retained in raw data; no predictions fabricated',
   'caption':'MVS-Synth sequence 0000, audit only; native units, not verified meters'}
 dump(target/'FIGURE_CONTRACT.json',contract)
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.colors import LogNorm
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
 fig,axs=plt.subplots(3,3,figsize=(12,7.5))
 for rr,fid in enumerate((0,49,99)):
  stem=f'{fid:04d}';image=np.asarray(Image.open(MVS/'0000/images'/(stem+'.png')))
  d=depth(MVS/'0000/depths'/(stem+'.exr')).astype(float);mask=np.isfinite(d)&(d>0)
  axs[rr,0].imshow(image);axs[rr,0].set_title('RGB '+stem)
  plot=axs[rr,1].imshow(np.ma.masked_where(~mask,d),norm=LogNorm(vmin=70,vmax=7000),cmap='viridis')
  axs[rr,1].set_title('GT depth (native units; log color)')
  axs[rr,2].imshow(mask,vmin=0,vmax=1,cmap='gray');axs[rr,2].set_title('Finite-positive mask')
  for ax in axs[rr]:ax.set_axis_off()
 fig.suptitle('MVS-Synth 0000 — real GT audit only; no Metric3D inference',fontsize=13)
 fig.tight_layout();fig.savefig(target/'R2_03_DATA_ALIGNMENT_EVIDENCE.png',dpi=160);fig.savefig(target/'R2_03_DATA_ALIGNMENT_EVIDENCE.svg');plt.close(fig)
 print(json.dumps({'audited_frames':len(rows),'protected_data_files':len(protected),'RGB_archives':len(archive_rows),
     'GT_alignment_diagnostics':comparisons,'independent_accuracy_evaluation_admitted':False},indent=2))

if __name__=='__main__':main()
