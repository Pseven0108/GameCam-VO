"""Read native EXR precision; do not alter GT or infer physical units."""
from common import *
import OpenEXR
def main():
    cpu_only();rows=[]
    for seq in ['0000','0001']:
        for stem in ['0000','0049','0099']:
            p=gt_dir(seq)/'depths'/(stem+'.exr')
            with OpenEXR.File(str(p),separate_channels=True) as f:
                a=f.channels()['Y'].pixels;v=a[np.isfinite(a)&(a>0)];med=np.median(v.astype(float));dtype=a.dtype
                step=float(np.spacing(np.asarray(med,dtype=dtype)))
                rows.append({'sequence':seq,'frame':stem,'reader_native_dtype':str(dtype),'median_native_depth':med,
                    'representable_spacing_near_median':step,'relative_spacing_near_median':step/med,
                    'EXR_sha256':sha(p),'physical_unit_known':False})
    dump(ROOT/'03_gt_audit/EXR_PRECISION_AUDIT.json',{'files':rows,
      'interpretation':'Representable source-depth precision is separate from photometric/geometric alignment and physical-scale truth; no GT conversion or denoising applied'})
    print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
