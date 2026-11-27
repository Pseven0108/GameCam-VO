"""Freeze 20 existing validation windows without consulting algorithm results.

One midpoint window from each of the first four constant-K complete sequences
per weather. Source camera records are strictly offline and never model input.
"""
import csv
import io
import json
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation

from common import TASK,sha,dump,csvwrite

BASE=Path('D:/aaa/GameCam-VO')
FRESH=BASE/'experiments/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408'
INVENTORY=BASE/'experiments/VIPER_DUAL_BASELINE_FULL_DATASET_STRATIFIED_R1/DATASET_SEQUENCE_INVENTORY.csv'
ARCHIVES=BASE/'downloads/VIPER_RGB_JPG_ORIGINALS_20261119/archives'


def main():
    out=TASK/'private/viper_inputs'
    if out.exists():raise FileExistsError('Frozen input output already exists; do not rewrite')
    out.mkdir(parents=True)
    rows=list(csv.DictReader(INVENTORY.open(encoding='utf-8-sig')))
    selected=[]
    for environment in ('Day','Sunset','Rain','Snow','Night'):
        eligible=sorted([r for r in rows if r['split']=='val' and r['environment']==environment
            and int(r['rgb_valid'])>=64 and int(r['gaps_inside_span'])==0
            and float(r['max_K_span_px'])<.001],key=lambda r:int(r['sequence_id']))
        if len(eligible)<4:raise RuntimeError('Insufficient fixed-K sequences in '+environment)
        for row in eligible[:4]:
            count=int(row['rgb_valid']);start=int(row['min_frame'])+(count-64)//2
            sid='val_'+row['sequence_id'];wid=sid+f'_{start:05d}-{start+63:05d}'
            selected.append(dict(window_id=wid,sequence=sid,environment=environment,
                rgb_start=start,rgb_end=start+63,frame_count=64,stride=1,
                camera_start=start-1,camera_end=start+62,
                selection='First four eligible sequence IDs per weather; arithmetic temporal midpoint; no model metric, GT motion or reliability used to choose',
                source_sequence_frames=count,source_K_span_px=float(row['max_K_span_px'])))
    needed={f"val/img/{r['sequence'][4:]}/{r['sequence'][4:]}_{f:05d}.jpg":(r,f) for r in selected for f in range(r['rgb_start'],r['rgb_end']+1)}
    index={};archive_records=[]
    for p in sorted(ARCHIVES.glob('val_img*.zip')):
        with zipfile.ZipFile(p) as z:
            members={info.filename:info for info in z.infolist()}
            hits=set(members)&set(needed)
            if not hits:continue
            record=dict(path=str(p),bytes=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns,target_members=len(hits))
            for name in sorted(hits):
                if name in index:raise RuntimeError('Duplicate source identity in archives: '+name)
                index[name]=dict(archive=str(p),crc32=f'{members[name].CRC:08x}',bytes=members[name].file_size)
            archive_records.append(record)
    if set(index)!=set(needed):raise RuntimeError('Missing selected original JPEG members: '+str(sorted(set(needed)-set(index))[:20]))
    # Freeze selection before image decoding and before any model comparison.
    csvwrite(TASK/'configs/VIPER_WINDOW_MANIFEST.csv',selected)
    dump(TASK/'configs/VIPER_SELECTION_FROZEN.json',dict(status='FROZEN_BEFORE_COMPARISON',windows=20,
        frames=1280,independent_sequences=20,weather_groups=5,source_inventory_sha256=sha(INVENTORY),
        source_inventory=str(INVENTORY),manifest_sha256=sha(TASK/'configs/VIPER_WINDOW_MANIFEST.csv'),
        previously_observed_data=True,new_blind_test=False,variable_K_sequences_excluded=['val_042','val_043']))
    image_rows=[];gt_rows=[];datasets=[]
    for row in selected:
        rgbdir=out/row['window_id']/'rgb';rgbdir.mkdir(parents=True)
        ids=np.arange(row['rgb_start'],row['rgb_end']+1)
        for fid in ids:
            member=f"val/img/{row['sequence'][4:]}/{row['sequence'][4:]}_{fid:05d}.jpg"
            entry=index[member]
            with zipfile.ZipFile(entry['archive']) as z:content=z.read(member) # zipfile verifies member CRC
            with Image.open(io.BytesIO(content)) as img:
                fmt,mode,size=img.format,img.mode,img.size;img.load()
            if fmt!='JPEG' or mode!='RGB' or size!=(1920,1080):raise RuntimeError('Unexpected original JPEG schema: '+member)
            dst=rgbdir/f'{fid:05d}.jpg';dst.write_bytes(content)
            image_rows.append(dict(window=row['window_id'],rgb_id=int(fid),member=member,
                archive=entry['archive'],bytes=len(content),crc32=entry['crc32'],sha256=sha(dst),decode='PASS',width=1920,height=1080))
        gt_path=FRESH/'offline_gt'/(row['sequence']+'.npz')
        with np.load(gt_path,allow_pickle=False) as z:
            by_id={int(x):i for i,x in enumerate(z['rgb_ids'])}
            where=np.array([by_id[int(i)] for i in ids]);camera=z['camera_ids'][where].copy()
            gt=z['gt_c2w'][where].copy();k=z['raw_intrinsics'][where].copy()
        if not np.array_equal(camera,ids-1) or not np.isfinite(gt).all() or not np.isfinite(k).all():
            raise RuntimeError('Frozen camera mapping or values invalid')
        span=float(np.max(np.abs(k-k[0])))
        if span>.001:raise RuntimeError('Variable input K in frozen window')
        k640=k[0].copy()/3.;k640[2:]=(k[0,2:]+.5)/3.-.5
        np.savez_compressed(out/row['window_id']/'offline_gt.npz',rgb_ids=ids,camera_ids=camera,gt_c2w=gt,raw_intrinsics=k)
        translations=np.linalg.norm(np.diff(gt[:,:3,3],axis=0),axis=1)
        angles=np.degrees(Rotation.from_matrix(gt[:-1,:3,:3].transpose(0,2,1)@gt[1:,:3,:3]).magnitude())
        gt_rows.append(dict(window=row['window_id'],source_path=str(gt_path),source_sha256=sha(gt_path),
            RGB_minus_1_exact=True,K_window_max_deviation=span,gt_unit='NATIVE_CAMERA_UNITS_NO_NEW_METRE_CLAIM',
            gt_path_length=float(translations.sum()),max_frame_translation=float(translations.max()),max_frame_rotation_deg=float(angles.max())))
        datasets.append(dict(**row,rgb_dir=str(rgbdir),offline_gt=str(out/row['window_id']/'offline_gt.npz'),
            K_640x360=k640.tolist(),resolution_hw=[360,640],interpolation='OpenCV INTER_LINEAR, half pixel centers, no crop'))
        print('FROZEN_WINDOW',row['window_id'],flush=True)
    csvwrite(out/'RGB_INTEGRITY.csv',image_rows);csvwrite(out/'CAMERA_ADMISSION.csv',gt_rows)
    dump(out/'SOURCE_ARCHIVES.json',archive_records)
    dump(TASK/'private/VIPER_INPUTS.json',dict(status='COMPLETE_INPUT_ADMISSION',windows=datasets,
        new_download_bytes=0,original_archives_modified=False,all_member_CRC_and_JPEG_decode_passed=True,
        extracted_images=len(image_rows),unique_image_hashes=len({r['sha256'] for r in image_rows}),
        selection_frozen_before_GT_motion_descriptors=True,production_baseline_modified=False))


if __name__=='__main__':main()
