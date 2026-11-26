"""Freeze samples before their predictions/GT errors are inspected."""
import hashlib,json,pathlib
from PIL import Image
from remote_io import ROOT,REMOTE_ROOT
from remote_start import cmd,upload
PROJECT=ROOT.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 manifests=PROJECT/'experiments/VIPER_MATCHED_DUAL_BASELINE_R2/manifests'
 samples=[];provenance=[]
 choices=[('Day','001'),('Night','007'),('Sunset','008'),('Rain','018'),('Snow','021')]
 for env,seq in choices:
  source=sorted(manifests.glob('val_'+seq+'_full_*.json'))[0]
  m=json.loads(source.read_text());assert m['environment']==env
  provenance.append({'path':str(source),'sha256':sha(source)})
  for frame in [m['frames'][0],m['frames'][len(m['frames'])//2]]:
   if seq=='007' and frame['rgb_id']==1:continue # Already measured in smoke.
   samples.append({'sample_id':'VIPER_'+env+'_val'+seq+'_'+f"{frame['rgb_id']:05d}",
    'dataset':'VIPER','sequence_id':'val_'+seq,'frame_id':f"{frame['rgb_id']:05d}",'environment':env,
    'rgb_path':'/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/val_'+seq+'/'+frame['file'],
    'rgb_sha256':frame['sha256'],'source_hw':m['raw_wh'][::-1],'input_hw':m['out_wh'][::-1],
    'fx':m['output_k'][0],'source_fx':m['fixed_source_k'][0],
    'input_protocol':'FROZEN_R2_640x360_INTER_LINEAR','role':'NO_DEPTH_GT_DISTRIBUTION_ONLY'})
 script="import pathlib; p=pathlib.Path("+repr(REMOTE_ROOT+'/inputs/mvs')+");p.mkdir(exist_ok=False)"
 cmd('exec env CUDA_VISIBLE_DEVICES= /usr/bin/python3 -B -',script.encode())
 for seq in ['0000','0001']:
  directory=PROJECT/'data/mvs_synth/GTAV_540'/seq if seq=='0000' else ROOT/'inputs/MVS-Synth/GTAV_540'/seq
  for frame in ['0000','0049','0099']:
   image=directory/'images'/(frame+'.png');pose=directory/'poses'/(frame+'.json')
   with Image.open(image) as im:im.load();width,height=im.size
   camera=json.loads(pose.read_text());destination=REMOTE_ROOT+'/inputs/mvs/'+seq+'_'+frame+'.png'
   transfer=upload(image,destination);provenance.append(transfer)
   samples.append({'sample_id':'MVS_'+seq+'_'+frame,'dataset':'MVS-Synth','sequence_id':seq,'frame_id':frame,
    'environment':'UNCLASSIFIED','rgb_path':destination,'rgb_sha256':sha(image),'source_hw':[height,width],
    'input_hw':[height,width],'fx':camera['f_x'],'source_fx':camera['f_x'],
    'input_protocol':'NATIVE_MVS_960x540_NO_INPUT_DOWNSAMPLE','role':'CALIBRATION' if seq=='0000' else 'TEST',
    'GT_depth_uploaded_to_model':False,'local_RGB_path':str(image),'local_pose_path':str(pose)})
 assert len(samples)==15
 out={'samples':samples,'total_unique_with_smoke':16,'selection':'First and temporal midpoint of first frozen segment per VIPER environment; MVS 0/49/99 fixed a priori',
      'sequence_split':{'Calibration':['0000'],'Test':['0001']},'input_provenance':provenance,
      'GT_units_status':'NOT_YET_ADMITTED','no_GT_error_based_selection':True,'full_VIPER_not_run':True}
 with (ROOT/'experiments/configs/PILOT_MANIFEST.json').open('x',encoding='utf-8') as f:f.write(json.dumps(out,indent=2)+'\n')
 print(json.dumps({'new_samples':15,'total_with_smoke':16,'VIPER_total':10,'MVS_total':6,'raw_depth_GT_transferred_to_GPU':False}))
if __name__=='__main__':main()
