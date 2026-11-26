"""Independent 200-frame GT/header, camera and cross-view alignment audit."""
import datetime,json,time
from PIL import Image
from scipy.ndimage import map_coordinates,sobel
from common import *
import OpenEXR

def header_value(v):
    if isinstance(v,np.ndarray): return v.tolist()
    if isinstance(v,(list,tuple)):return [header_value(x) for x in v]
    if isinstance(v,(str,float,int,bool)) or v is None:return v
    return str(v)

def crossview(directory,s,t,kind='z',center=0.,inverse_extrinsic=False,gt_multiplier=1.,include_photo=False):
    ds=depth(directory/'depths'/f'{s:04d}.exr')*gt_multiplier
    dt=depth(directory/'depths'/f'{t:04d}.exr')*gt_multiplier
    ks,es=camera(directory/'poses'/f'{s:04d}.json');kt,et=camera(directory/'poses'/f'{t:04d}.json')
    transform=np.linalg.inv(et)@es if inverse_extrinsic else et@np.linalg.inv(es)
    yy,xx=np.mgrid[4:ds.shape[0]-4:8,4:ds.shape[1]-4:8]
    z=ds[yy,xx];valid=np.isfinite(z)&(z>0)
    u0=xx[valid].astype(float)+center;v0=yy[valid].astype(float)+center
    rays=np.linalg.solve(ks,np.vstack([u0,v0,np.ones(valid.sum())]))
    if kind=='range':rays/=np.linalg.norm(rays,axis=0)
    xyz=transform[:3,:3]@(rays*z[valid])+transform[:3,3,None]
    q=kt@xyz;u=q[0]/q[2]-center;v=q[1]/q[2]-center
    ok=np.isfinite(u)&np.isfinite(v)&(xyz[2]>0)&(u>=0)&(u<dt.shape[1]-1)&(v>=0)&(v<dt.shape[0]-1)
    obs=dt[np.rint(v[ok]).astype(int),np.rint(u[ok]).astype(int)]
    pred=xyz[2,ok] if kind=='z' else np.linalg.norm(xyz[:,ok],axis=0)
    positive=np.isfinite(obs)&(obs>0);err=np.abs(pred[positive]-obs[positive])/obs[positive]
    row={'sequence':directory.name,'source':f'{s:04d}','target':f'{t:04d}','depth_hypothesis':kind,
        'pixel_center_offset':center,'extrinsic_convention':'C2W_HYPOTHESIS' if inverse_extrinsic else 'W2C',
        'GT_multiplier_only_not_translation':gt_multiplier,'points_source_valid':int(valid.sum()),'points_positive_target':len(err),
        'median_relative_depth_disagreement':float(np.median(err)),'P90':float(np.percentile(err,90)),
        'fraction_depth_disagreement_lt_1pct':float((err<.01).mean()),'physical_units_proven':False}
    if include_photo:
        a=np.asarray(Image.open(directory/'images'/f'{s:04d}.png').convert('RGB'),float)/255.
        b=np.asarray(Image.open(directory/'images'/f'{t:04d}.png').convert('RGB'),float)/255.
        uv=np.array([v[ok][positive],u[ok][positive]])
        reconstructed=np.stack([map_coordinates(b[:,:,c],uv,order=1,mode='nearest',prefilter=False) for c in range(3)],1)
        direct=a[yy[valid][ok][positive],xx[valid][ok][positive]]
        unwarped=b[yy[valid][ok][positive],xx[valid][ok][positive]]
        visible=err<.01
        photo=np.abs(reconstructed-direct).mean(1);control=np.abs(unwarped-direct).mean(1)
        row.update(photometric_visible_points=int(visible.sum()),
          median_RGB_abs_warp_error_all=float(np.median(photo)),
          median_RGB_abs_warp_error_depth_consistent=float(np.median(photo[visible])) if visible.any() else None,
          median_RGB_abs_unwarped_error_depth_consistent=float(np.median(control[visible])) if visible.any() else None,
          photo_is_alignment_diagnostic_not_accuracy_or_sync_proof=True)
    return row

def main():
    cpu_only();start=time.perf_counter();rows=[];headers=[];matrices=[];cross=[]
    for seq in ['0000','0001']:
        directory=gt_dir(seq)
        for i in range(100):
            stem=f'{i:04d}';ip=directory/'images'/(stem+'.png');dp=directory/'depths'/(stem+'.exr');cp=directory/'poses'/(stem+'.json')
            with Image.open(ip) as im:im.load();size=im.size;mode=im.mode
            with OpenEXR.File(str(dp),separate_channels=True) as f:
                header=f.header();channels=f.channels();d=channels['Y'].pixels.astype(np.float64)
                names=sorted(channels);dw=header['dataWindow'];display=header['displayWindow']
                dw0=np.asarray(dw[0]);dw1=np.asarray(dw[1]);dis0=np.asarray(display[0]);dis1=np.asarray(display[1])
                hs={k:header_value(v) for k,v in header.items() if k!='channels'}
            k,e=camera(cp);r=e[:3,:3]
            valid=np.isfinite(d)&(d>0);finite=d[np.isfinite(d)]
            if size!=(960,540) or d.shape!=(540,960) or mode!='RGB' or names!=['Y']:raise RuntimeError('RGB/GT layout differs')
            if not np.array_equal(dw0,[0,0]) or not np.array_equal(dw1,[959,539]):raise RuntimeError('Nonzero EXR data window origin')
            if not np.array_equal(dis0,dw0) or not np.array_equal(dis1,dw1):raise RuntimeError('EXR display/dataWindow differ')
            rows.append({'sequence':seq,'frame':stem,'RGB_width':size[0],'RGB_height':size[1],'GT_width':d.shape[1],'GT_height':d.shape[0],
             'RGB_mode':mode,'GT_channel':'Y','GT_finite_positive':int(valid.sum()),'GT_zero':int((d==0).sum()),
             'GT_negative_finite':int(((d<0)&np.isfinite(d)).sum()),'GT_posInf':int(np.isposinf(d).sum()),'GT_negInf':int(np.isneginf(d).sum()),'GT_NaN':int(np.isnan(d).sum()),
             'GT_min_finite':float(finite.min()),'GT_median_finite':float(np.median(finite)),'GT_max_finite':float(finite.max()),
             'fx':k[0,0],'fy':k[1,1],'cx':k[0,2],'cy':k[1,2],'rotation_det':float(np.linalg.det(r)),
             'rotation_orthogonality_Fro':float(np.linalg.norm(r.T@r-np.eye(3))),
             'data_window_origin_x':int(dw0[0]),'data_window_origin_y':int(dw0[1]),
             'RGB_sha256':sha(ip),'GT_sha256':sha(dp),'pose_sha256':sha(cp),'physical_units':'UNKNOWN_NATIVE_UNITS'})
            headers.append({'sequence':seq,'frame':stem,'header':hs,'unit_named_attributes':[key for key in hs if any(word in key.lower() for word in ['unit','meter','scale'])]})
            if i in [0,49,99]: matrices.append({'sequence':seq,'frame':stem,'K':k.tolist(),'W2C':e.tolist()})
        for s in range(99):cross.append(crossview(directory,s,s+1))
        print('GT_AUDITED',seq,100,flush=True)
    selected=[]
    for seq in ['0000','0001']:
        d=gt_dir(seq)
        for s,t in [(0,1),(49,50),(98,99)]:
            for kind in ['z','range']:
                selected.append(crossview(d,s,t,kind=kind,include_photo=True))
            for center in [-.5,.5]:selected.append(crossview(d,s,t,center=center,include_photo=True))
            selected.append(crossview(d,s,t,inverse_extrinsic=True))
            # Only GT rescaled while native pose translation stays fixed. This
            # can check internal GT/pose consistency, never assign a meter unit.
            for multiplier in [.1,10.]:selected.append(crossview(d,s,t,gt_multiplier=multiplier))
    csvwrite(ROOT/'03_gt_audit/FULL_200_FRAME_METADATA_AUDIT.csv',rows)
    csvwrite(ROOT/'03_gt_audit/ALL_198_ADJACENT_Z_DEPTH_PAIRS.csv',cross)
    csvwrite(ROOT/'03_gt_audit/GEOMETRY_CONVENTION_CONTROLS.csv',selected)
    dump(ROOT/'03_gt_audit/EXR_HEADERS.json',{'headers':headers})
    dump(ROOT/'03_gt_audit/PILOT_CAMERA_MATRICES.json',{'frames':matrices})
    summary={'RGB_frames':200,'GT_frames':200,'pose_records':200,'all_native_shapes_match':True,'all_EXR_origins_zero':True,
      'GT_finite_positive':sum(r['GT_finite_positive'] for r in rows),'GT_zeros':sum(r['GT_zero'] for r in rows),
      'GT_negative_finite':sum(r['GT_negative_finite'] for r in rows),'GT_posInf':sum(r['GT_posInf'] for r in rows),
      'GT_negInf':sum(r['GT_negInf'] for r in rows),'GT_NaN':sum(r['GT_NaN'] for r in rows),
      'headers_with_unit_attributes':sum(bool(h['unit_named_attributes']) for h in headers),
      'physical_metric_unit':'NOT_ESTABLISHED','Inf_semantics':'Nonfinite/unusable depth; sky/background interpretation requires scene inspection, not converted to finite depth',
      'zero_semantics':'No raw GT zeros observed in the 200 audited maps; no inference about unseen files',
      'all_adjacent_pairs':len(cross),'selected_hypothesis_pairs':len(selected),
      'median_of_pair_median_relative_Z_disagreement':float(np.median([r['median_relative_depth_disagreement'] for r in cross])),
      'pixel_clock_sync_proven':False,'occlusion_mask_supplied':False,'new_dataset_downloaded':False,'elapsed_CPU_seconds':time.perf_counter()-start}
    dump(ROOT/'03_gt_audit/GT_QUALITY_SUMMARY.json',summary);print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
