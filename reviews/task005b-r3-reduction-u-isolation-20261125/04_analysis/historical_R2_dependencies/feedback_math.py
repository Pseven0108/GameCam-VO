"""Independent CPU feedback reconstruction from sealed tensor bytes, no torch."""
import os,sys,pathlib,json,tarfile,gzip,zipfile,io,tempfile,csv,itertools,hashlib
os.environ['CUDA_VISIBLE_DEVICES']=''
sys.path.insert(0,r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125\cpu_plot_dependencies')
import numpy as np
from analyze_pairs import ROOT,RECV,compare,save_csv,FINAL
SNAP=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-GPU-20261125-R1\snapshot_D0_S1_RGB233.tar')
def read_dino(kx):
 with tarfile.open(SNAP) as archive:
  mn=next(n for n in archive.getnames() if n.endswith('/manifest.json'));m=json.load(archive.extractfile(mn))
  node=next(n for n in m['nodes'].values() if n.get('kind')=='tensor' and n.get('shape')==[500,384,45,80])
  storage=m['storages'][node['storage']]
  member=next(n for n in archive.getnames() if n.endswith('/'+storage['file']))
  # Owned temporary file is removed by the context manager; original stays read-only.
  with tempfile.TemporaryFile(dir=RECV.parents[1]) as spool:
   with gzip.GzipFile(fileobj=archive.extractfile(member)) as stream:
    while True:
     b=stream.read(8*1024**2)
     if not b:break
     spool.write(b)
   spool.seek(0)
   with zipfile.ZipFile(spool) as z:
    raw=next(n for n in z.namelist() if '/data/' in n and n.rsplit('/',1)[1].isdigit())
    info=z.getinfo(raw);assert info.file_size==storage['byte_size']
    with z.open(raw) as f:
     rows=[]
     for k in kx:
      f.seek(int(k)*384*45*80*4)
      rows.append(np.frombuffer(f.read(384*45*80*4),dtype='<f4').copy().reshape(384,3600))
    return np.stack(rows),{'snapshot_state_sha256':m['state_sha256'],'storage_raw_sha256':storage['raw_sha256'],'selected_slot_ids':kx.tolist(),'selected_feature_bytes':len(rows)*384*3600*4,'temporary_full_zip_not_retained':True}
def main():
 data={p.stem:dict(np.load(p,allow_pickle=False)) for p in (RECV/'trace').glob('*.npz')}
 first=next(iter(data.values()));kx=first['iter1_kx'];features,proof=read_dino(kx)
 rows=[]
 for tag,a in data.items():
  for it in (1,2):
   pref=f'iter{it}_';J=a[pref+'J_linear'];du=a[pref+'affine_du'];before=a[pref+'affine_before_linear'];after=a[pref+'affine_after']
   # Match the ATen update expression using float32 operations, not a fused formula.
   rec_du=np.float32(-0.1)*J.mean(axis=0,dtype=np.float32)
   rec_after=before+(du-np.float32(0.002)*before)
   for name,actual,ref in [('affine_du_from_J_linear',du,rec_du),('affine_after_from_native_du',after,rec_after)]:rows.append({'tag':tag,'iteration':it,'quantity':name,**compare(actual,ref)})
   predicted_temp=np.einsum('c,kcp->kp',after[:-1].astype('f8'),features.astype('f8'),optimize=True)+float(after[-1])
   predicted_U=np.log(1.1+np.exp(predicted_temp))
   for name,actual,ref in [('temp_from_affine_FP64_formula',a[pref+'temp_after'][kx].reshape(len(kx),-1),predicted_temp.astype('f4')),('U_from_affine_FP64_formula',a[pref+'U_after'][kx].reshape(len(kx),-1),predicted_U.astype('f4'))]:rows.append({'tag':tag,'iteration':it,'quantity':name,**compare(actual,ref)})
   # CPU FP64 reduction reference: native atomic float32 is NOT expected bit-identical.
   total=a[pref+'J_total'].astype('f8');temp=a[pref+'temp_before_linear'][kx].reshape(len(kx),-1).astype('f8')
   dldy=total/(1.+1.1*np.exp(-temp))
   jref=np.concatenate([np.einsum('kp,kcp->kc',dldy,features.astype('f8'),optimize=True),dldy.sum(axis=1)[:,None]],axis=1)/3600.
   rows.append({'tag':tag,'iteration':it,'quantity':'J_linear_vs_FP64_reduction_reference',**compare(J,jref.astype('f4'))})
 save_csv('FEEDBACK_RECONSTRUCTION.csv',rows)
 pairs=[]
 for left,right in itertools.combinations(data,2):
  a,b=data[left],data[right]
  geom=['poses_before','disps_before','U_before','temp_before','affine_before','Cii_geometry','wi_geometry','Hs_geometry','vs_geometry','C','w','Q','dx','dz','poses_after_geometry','disps_after_geometry','Jii_data']
  pairs.append({'left':left,'right':right,'first_iteration_before_Jjj_all_bitwise_equal':all(np.array_equal(a['iter1_'+n],b['iter1_'+n]) for n in geom),'first_diff_is_Jjj':not np.array_equal(a['iter1_Jjj_data'],b['iter1_Jjj_data']),'first_iter_J_linear_bitwise_equal':np.array_equal(a['iter1_J_linear'],b['iter1_J_linear']),'first_iter_affine_changed':int(np.count_nonzero(a['iter1_affine_after']!=b['iter1_affine_after'])),'second_iteration_pose_input_identical':np.array_equal(a['iter2_poses_before'],b['iter2_poses_before']),'second_iteration_disp_input_identical':np.array_equal(a['iter2_disps_before'],b['iter2_disps_before']),'feedback_seam_in_call_bitwise_equal':all(np.array_equal(a['iter1_'+x],a['iter2_'+y]) for x,y in [('U_after','U_before'),('temp_after','temp_before'),('affine_after','affine_before')]),'final_endpoints_PASS':all(compare(a[n],b[n])['PASS'] for n in FINAL)})
 save_csv('FEEDBACK_CHAIN_PAIRS.csv',pairs)
 # Cross-observer final endpoints, keeping uninstrumented and observed groups explicit.
 plain={p.stem:dict(np.load(p,allow_pickle=False)) for p in (RECV/'plain').glob('*.npz')}
 cross=[]
 for left,a in plain.items():
  for right,b in data.items():
   for n in FINAL:cross.append({'left':left,'right':right,'field':n,**compare(a[n],b[n])})
 save_csv('OBSERVER_EFFECT_ENDPOINTS.csv',cross)
 result={'source':proof,'reconstruction_rows':len(rows),'all_reconstruction_original_tolerance_pass':all(x['PASS'] for x in rows),'cross_pair_chain':pairs,'trace_final_endpoints_all_pass':all(x['final_endpoints_PASS'] for x in pairs),'formula_note':'FP64 sums are independent reference values, not a bitwise model of CUDA FMA and float atomic addition. No evidence was substituted.'}
 (ROOT/'04_analysis/FEEDBACK_CHAIN_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
