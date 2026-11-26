"""Expose motion strength and whether cross-view controls are informative."""
from common import *
from audit_gt import crossview
def main():
    cpu_only();rows=[];controls=[]
    for seq in ['0000','0001']:
        directory=gt_dir(seq)
        own=[]
        for s in range(99):
            _,a=camera(directory/'poses'/f'{s:04d}.json');_,b=camera(directory/'poses'/f'{s+1:04d}.json');t=b@np.linalg.inv(a)
            distance=float(np.linalg.norm(t[:3,3]));angle=float(np.arccos(np.clip((np.trace(t[:3,:3])-1)/2,-1,1)))
            own.append({'sequence':seq,'source':f'{s:04d}','target':f'{s+1:04d}','translation_native':distance,'rotation_radians':angle,
             'rotation_dominant_or_stationary':distance<1e-5,'unit_scale_from_rotation_alone_identifiable':False})
        rows.extend(own)
        strongest=max(own,key=lambda r:r['translation_native']);s=int(strongest['source'])
        for kind in ['z','range']:
            x=crossview(directory,s,s+1,kind=kind,include_photo=True);controls.append({**x,'selection':'Maximum adjacent camera translation using poses only',
                 'translation_native':strongest['translation_native'],'rotation_radians':strongest['rotation_radians']})
        for multiplier in [.1,10.]:
            x=crossview(directory,s,s+1,gt_multiplier=multiplier);controls.append({**x,'selection':'Maximum adjacent camera translation using poses only',
                 'translation_native':strongest['translation_native'],'rotation_radians':strongest['rotation_radians']})
    csvwrite(ROOT/'03_gt_audit/ADJACENT_MOTION_CONDITIONING.csv',rows)
    csvwrite(ROOT/'03_gt_audit/MAX_TRANSLATION_ALIGNMENT_CONTROLS.csv',controls)
    summary=[]
    for seq in ['0000','0001']:
        own=[r for r in rows if r['sequence']==seq]
        summary.append({'sequence':seq,'translation_native_min':min(r['translation_native'] for r in own),
          'translation_native_median':float(np.median([r['translation_native'] for r in own])),
          'translation_native_max':max(r['translation_native'] for r in own),
          'pairs_translation_below_1e_minus5':sum(r['translation_native']<1e-5 for r in own),
          'max_rotation_radians':max(r['rotation_radians'] for r in own),
          'geometric_scale_is_physical_meter_proof':False})
    dump(ROOT/'03_gt_audit/MOTION_CONDITIONING_SUMMARY.json',{'sequences':summary,'why':'Near-static views cannot identify a depth/translation scale mismatch; scaling depth and translation together leaves projection unchanged'})
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
