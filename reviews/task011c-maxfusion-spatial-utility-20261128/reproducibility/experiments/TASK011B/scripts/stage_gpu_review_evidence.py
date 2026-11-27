"""Stage real numerical/log evidence; never publish RGB embedded in video.npz.

Original complete archives remain on D:. The published native grid is a lossless
selection at the exact disparity sample coordinates, not a recomputed model or
an image resize. Full-resolution confidence rankings are computed before that
selection so reviewer-side BA coefficients reproduce the actual controller.
"""
import argparse, json, shutil, sys, zipfile
from pathlib import Path
import numpy as np

from common import ROOT, TASK, dump, sha

sys.path.insert(0, str(TASK/'CADP_DR_EXPERIMENTAL_BRANCH'))
from controller import coefficient_map, arm_config

REVIEW=ROOT/'reviews/task011b-validity-aware-cadp-dr-20261127'
GRID=(slice(3,361,8),slice(3,641,8))


def copy(source,dest):
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        if sha(dest)!=sha(source):
            raise RuntimeError('Preserve different staged evidence '+str(dest))
    else:
        shutil.copy2(source,dest)


def stage_window(receipt_path):
    receipt=json.loads(receipt_path.read_text())
    if not receipt['all_internal_SHA256']:
        raise RuntimeError('Unverified source output')
    label=receipt_path.stem
    source=Path(receipt['local_extracted'])
    dest=REVIEW/'04_R3_VIPER_EVALUATION/evidence/windows'/label
    if (dest/'REVIEW_DERIVATION.json').exists():
        return
    dest.mkdir(parents=True,exist_ok=True)
    copied=[]
    for p in sorted(source.rglob('*')):
        if not p.is_file() or p.name=='video.npz':
            continue
        rel=p.relative_to(source)
        copy(p,dest/rel)
        copied.append(dict(path=str(rel).replace('\\','/'),bytes=p.stat().st_size,sha256=sha(p)))
    original=source/'native/video.npz'
    numeric=None
    if original.exists():
        values={}
        with np.load(original,allow_pickle=False) as z:
            for k in ('timestamps','poses','tum_poses','droid_disps','intrinsics','uncertainties'):
                values[k]=z[k].copy()
            # Native saves mono_disps at 360x640; BA reads the exact 3+8n grid.
            values['mono_disps_native_grid']=z['mono_disps'][:,GRID[0],GRID[1]].copy()
            if values['mono_disps_native_grid'].shape!=values['droid_disps'].shape:
                raise RuntimeError('Native saved video grid differs')
        numeric=dest/'keyframe_state_ba_grid.npz'
        np.savez_compressed(numeric,**values)
    for suffix in ('stdout','stderr'):
        p=TASK/'gpu_results/service_logs'/(label+'.'+suffix)
        if p.exists():copy(p,dest/'service'/p.name)
    copy(receipt_path,dest/'TRANSFER_RECEIPT.json')
    dump(dest/'REVIEW_DERIVATION.json',dict(
        complete_original_archive_sha256=receipt['sha256'],
        copied_original_files=copied,
        saved_video_sha256=sha(original) if original.exists() else None,
        published_numerical_state=numeric.name if numeric else None,
        numerical_state_sha256=sha(numeric) if numeric else None,
        sampling=dict(y_start=3,y_step=8,x_start=3,x_step=8,shape=[45,80]),
        omitted_from_publication=['native/video.npz: embedded raw RGB, full-resolution duplicate disparity fields'],
        original_full_archive_retained_locally=True,
        final_frame_poses_and_native_disparity_and_U_unmodified=True))
    print('STAGED_ACTUAL_WINDOW_EVIDENCE',label,flush=True)


def stage_cache(receipt_path):
    receipt=json.loads(receipt_path.read_text());label=receipt_path.stem
    source=Path(receipt['local_extracted'])
    dest=REVIEW/'04_R3_VIPER_EVALUATION/evidence/priors'/label
    if (dest/'REVIEW_DERIVATION.json').exists():return
    if not receipt['all_internal_SHA256']:raise RuntimeError('Unverified prior cache')
    dest.mkdir(parents=True,exist_ok=True)
    meta=json.loads((source/'CACHE_RECEIPT.json').read_text())
    if meta.get('precision_protocol')!='NATIVE_MOTION_FILTER_AUTOCAST_V2':
        raise RuntimeError('Engineering cache cannot be staged as formal')
    derivations=[]
    for record in meta['records']:
        p=source/f'{record["timestamp"]:05d}.npz'
        if sha(p)!=record['sha256']:raise RuntimeError('Original cache hash changed')
        with np.load(p,allow_pickle=False) as z:
            d=z['native_depth'].copy();flip=z['flip_depth'][:,::-1].copy()
            confidence=z['native_confidence'].copy();pair=z['tta_valid'].copy()
            data=dict(native_depth=d[GRID].copy(),flip_depth_aligned=flip[GRID].copy(),
                native_confidence=confidence[GRID].copy(),
                flip_confidence_aligned=z['flip_confidence'][:,::-1][GRID].copy(),
                tta_valid=pair[GRID].copy())
            for arm in ('A0','A1','A2','A3','A4','A5','A6'):
                coeff,counts=coefficient_map(d,flip,confidence,pair,arm_config(arm))
                data['coefficient_'+arm]=coeff[GRID].astype(np.float32)
        target=dest/p.name
        np.savez_compressed(target,**data)
        derivations.append(dict(timestamp=record['timestamp'],rgb_id=record['rgb_id'],
            original_full_resolution_sha256=record['sha256'],
            published_grid_path=p.name,published_grid_sha256=sha(target)))
    for filename in ('CACHE_RECEIPT.json','OUTPUT_SHA256.json'):
        copy(source/filename,dest/filename)
    copy(receipt_path,dest/'TRANSFER_RECEIPT.json')
    dump(dest/'REVIEW_DERIVATION.json',dict(
        frames=len(derivations),source_archive_sha256=receipt['sha256'],derivations=derivations,
        original_full_resolution_predictions_retained_locally=True,
        exact_float32_coefficients_used_by_native_grid=True,
        full_resolution_ranks_computed_before_sampling=True,
        raw_RGB_included=False,full_resolution_prior_arrays_not_published=True,
        grid=dict(y_start=3,y_step=8,x_start=3,x_step=8,shape=[45,80])))
    print('STAGED_ACTUAL_PRIOR_EVIDENCE',label,flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true')
    a=parser.parse_args()
    receipts=sorted((TASK/'gpu_results/receipts').glob('*.json'))
    windows=[p for p in receipts if p.stem.startswith('window_')]
    caches=[p for p in receipts if p.stem.startswith('cache_')]
    for p in windows:stage_window(p)
    for p in caches:stage_cache(p)
    dump(REVIEW/'04_R3_VIPER_EVALUATION/evidence/STAGING_PROGRESS.json',dict(
        actual_windows=len(windows),actual_caches=len(caches),planned_windows=140,
        complete=len(windows)==140,original_dataset_excluded=True))
    if not a.partial and (len(windows)!=140 or len(caches)!=20):
        raise RuntimeError('Full staging requires all planned formal outcomes')
    print('REAL_EVIDENCE_STAGED',len(windows),len(caches),flush=True)


if __name__=='__main__':main()
