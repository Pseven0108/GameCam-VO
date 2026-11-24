# 精确源码节选

来源：D:\aaa\GameCam-VO\experiments\DROID_W_TASK004C_B_IO_COMPAT_20261124_R1\raw_evidence\R3_OFFLINE\additional_source_reference\task003_observer.py

SHA-256：1d9173fad166f2563d68a010b8efe98ff326ecf24d54ec4b265a80107a4abea6

```text
78:     return x+q[..., 3:4]*uv+np.cross(q[..., :3],uv)
79: 
80: 
81: def geometry(k, poses, disps, u, ii, jj, target, weight, enabled, target_enabled):
82:     """CPU reconstruction of a sampled native projection at one call boundary."""
83:     if target_enabled:
84:         raise ValueError('target uncertainty is outside the sealed Task 003 contract')
85:     if not np.isfinite(k).all() or min(k[:2]) <= 0:
86:         raise ValueError('invalid backend calibration')
87:     fx, fy, cx, cy = k
88:     h, w = disps.shape[1:]
89:     y, x = np.mgrid[:h,:w]*GRID_STEP
90:     rays = np.stack(((x-cx)/fx,(y-cy)/fy,np.ones_like(x)), axis=-1)
91:     a, b = poses[ii], poses[jj]
92:     q = mul(b[:,3:],conj(a[:,3:]))
93:     t = b[:,:3]-rotate(q,a[:,:3])
94:     # This branch mirrors the native ix == jx fixed stereo offset.
95:     t[ii==jj] = [-.1,0,0]
96:     q[ii==jj] = [0,0,0,1]
97:     warped = rotate(q[:,None,None,:],rays)+disps[ii,...,None]*t[:,None,None,:]
98:     z = warped[...,2]
99:     valid = np.isfinite(warped).all(axis=-1)&(z>=.25) & np.isfinite(target).all(-1)
100:     inv = np.divide(1.,z,out=np.zeros_like(z),where=valid)
101:     repro = warped[...,:2]*inv[...,None]*[fx,fy]+[cx,cy]
102:     residual = target-repro
103:     factor = np.fmax(np.fmin(1./np.fmax(45.*u[ii]-35.,.1),1.),0.) if enabled else np.ones_like(z)
104:     effective = np.where(valid[...,None],.001*weight*factor[...,None],0.)
105:     usable_weight = np.isfinite(effective).all(-1) & (effective>=0).all(-1)
106:     live = valid & usable_weight & (effective>0).any(-1)
107:     zero = valid & usable_weight & (effective==0).all(-1)
108:     return dict(coverage='DETERMINISTIC_EDGE_AND_PIXEL_SUBSAMPLE', arithmetic='CPU_RECONSTRUCTION',
109:                 sampled_pixels=int(valid.size), valid_projection_samples=int(valid.sum()),
110:                 positive_weight_observation_samples=int(live.sum()),
111:                 zero_weight_valid_projection_samples=int(zero.sum()),
112:                 invalid_weight_valid_projection_samples=int((valid & ~usable_weight).sum()),
113:                 valid_fraction=float(valid.mean()) if valid.size else None,
114:                 residual_lowres_px=stats(np.linalg.norm(residual[valid],axis=-1)),
115:                 raw_weight=stats(weight), effective_weight=stats(effective),
116:                 source_uncertainty_multiplier=stats(factor),
117:                 weighted_residual_sse=float(np.sum(effective[live]*residual[live]**2)))
118: 
```
