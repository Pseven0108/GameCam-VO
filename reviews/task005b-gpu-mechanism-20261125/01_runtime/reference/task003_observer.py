"""Task 003 event writer: read existing tensors; do not import torch or SLAM."""
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from time import perf_counter_ns, time_ns

import numpy as np


FOCUS = frozenset((301, 309, 312, 325, 328, 353))
EDGE_LIMIT = 24
GRID_STEP = 4
SCHEMA = 'GAMECAM_TASK004_RUNTIME_OBSERVER_CANDIDATE_V1'


def integer(value):
    n = int(value)
    if n != value:
        raise ValueError(f'non-integer original index: {value}')
    return n


def rgb(local_index):
    idx = integer(local_index)
    if not 0 <= idx < 487:
        raise ValueError(f'RGB index outside exact Task 003 input: {idx}')
    return idx + 1


def safe(value):
    """Preserve invalid numerics as JSON null without dropping the observation."""
    if isinstance(value, np.ndarray):
        return safe(value.tolist())
    if isinstance(value, np.generic):
        return safe(value.item())
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, dict):
        return {key: safe(v) for key, v in value.items()}
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def stats(value):
    a = np.asarray(value).reshape(-1)
    finite = a[np.isfinite(a)]
    positive = int((finite>0).sum())
    result = dict(n=int(a.size), finite=int(finite.size), positive=positive,
                  positive_fraction=float(positive/a.size) if a.size else None,
                  negative=int((finite < 0).sum()), minimum=None, maximum=None, mean=None,
                  p05=None, median=None, p90=None, p95=None)
    if finite.size:
        bounds = np.quantile(finite, [0,.05,.5,.90,.95,1])
        result.update(zip(('minimum','p05','median','p90','p95','maximum'), map(float,bounds)))
        result['mean'] = float(finite.mean(dtype=np.float64))
    return result


def depth_from_disp(value):
    d = value[np.isfinite(value)&(value>0)].astype(np.float64)
    return stats(1./d)


def mul(q, r):
    u, x = q[..., :3], r[..., :3]
    v, y = q[..., 3:4], r[..., 3:4]
    return np.concatenate((v*x+y*u+np.cross(u,x), v*y-np.sum(u*x,axis=-1,keepdims=True)), axis=-1)


def conj(q):
    return q*np.asarray([-1,-1,-1,1])


def rotate(q, x):
    uv = 2*np.cross(q[..., :3],x)
    return x+q[..., 3:4]*uv+np.cross(q[..., :3],uv)


def geometry(k, poses, disps, u, ii, jj, target, weight, enabled, target_enabled):
    """CPU reconstruction of a sampled native projection at one call boundary."""
    if target_enabled:
        raise ValueError('target uncertainty is outside the sealed Task 003 contract')
    if not np.isfinite(k).all() or min(k[:2]) <= 0:
        raise ValueError('invalid backend calibration')
    fx, fy, cx, cy = k
    h, w = disps.shape[1:]
    y, x = np.mgrid[:h,:w]*GRID_STEP
    rays = np.stack(((x-cx)/fx,(y-cy)/fy,np.ones_like(x)), axis=-1)
    a, b = poses[ii], poses[jj]
    q = mul(b[:,3:],conj(a[:,3:]))
    t = b[:,:3]-rotate(q,a[:,:3])
    # This branch mirrors the native ix == jx fixed stereo offset.
    t[ii==jj] = [-.1,0,0]
    q[ii==jj] = [0,0,0,1]
    warped = rotate(q[:,None,None,:],rays)+disps[ii,...,None]*t[:,None,None,:]
    z = warped[...,2]
    valid = np.isfinite(warped).all(axis=-1)&(z>=.25) & np.isfinite(target).all(-1)
    inv = np.divide(1.,z,out=np.zeros_like(z),where=valid)
    repro = warped[...,:2]*inv[...,None]*[fx,fy]+[cx,cy]
    residual = target-repro
    factor = np.fmax(np.fmin(1./np.fmax(45.*u[ii]-35.,.1),1.),0.) if enabled else np.ones_like(z)
    effective = np.where(valid[...,None],.001*weight*factor[...,None],0.)
    usable_weight = np.isfinite(effective).all(-1) & (effective>=0).all(-1)
    live = valid & usable_weight & (effective>0).any(-1)
    zero = valid & usable_weight & (effective==0).all(-1)
    return dict(coverage='DETERMINISTIC_EDGE_AND_PIXEL_SUBSAMPLE', arithmetic='CPU_RECONSTRUCTION',
                sampled_pixels=int(valid.size), valid_projection_samples=int(valid.sum()),
                positive_weight_observation_samples=int(live.sum()),
                zero_weight_valid_projection_samples=int(zero.sum()),
                invalid_weight_valid_projection_samples=int((valid & ~usable_weight).sum()),
                valid_fraction=float(valid.mean()) if valid.size else None,
                residual_lowres_px=stats(np.linalg.norm(residual[valid],axis=-1)),
                raw_weight=stats(weight), effective_weight=stats(effective),
                source_uncertainty_multiplier=stats(factor),
                weighted_residual_sse=float(np.sum(effective[live]*residual[live]**2)))


def sample_edges(ii, jj, ids):
    if len(ii)<=EDGE_LIMIT:
        return list(range(len(ii)))
    focus = [e for e,(i,j) in enumerate(zip(ii,jj)) if ids[i] in FOCUS or ids[j] in FOCUS]

    def spread(pool, n):
        return [pool[i] for i in np.linspace(0,len(pool)-1,min(n,len(pool)),dtype=int)] if pool else []

    priority = spread(focus, EDGE_LIMIT//2)
    remainder = [i for i in range(len(ii)) if i not in priority]
    return sorted(priority+spread(remainder,EDGE_LIMIT-len(priority)))


@dataclass
class Recorder:
    path: Path
    stage: str = 'startup'
    frame_id: object = None
    batch: int = 0
    current_step: object = None
    filler_n: object = None
    ord: int = 0
    ba_id: int = 0
    copy_ns: int = 0
    bytes_out: int = 0
    before: dict = field(default_factory=dict)
    max_bytes: int = 384 * 1024 * 1024
    _file: object = None
    added: bool = False
    io_ns_total: int = 0
    capture_ns_total: int = 0
    copy_ns_total: int = 0

    def array(self,x):
        start = perf_counter_ns()
        value = x if isinstance(x,np.ndarray) else x.detach().cpu().numpy()
        self.copy_ns += perf_counter_ns()-start
        return np.asarray(value)

    def emit(self,name,start,**data):
        self.ord += 1
        captured = perf_counter_ns()-start
        row = dict(schema=SCHEMA,event=self.ord,type=name,pid=os.getpid(),time_unix_ns=time_ns(),
                   stage=self.stage, trigger_rgb_id=self.frame_id, outer_iteration=self.current_step,
                   filler_batch=self.batch if self.filler_n is not None else None,
                   capture_and_summary_ns=captured,copy_to_cpu_ns=self.copy_ns,**data)
        started_io = perf_counter_ns()
        line = json.dumps(safe(row),allow_nan=False,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n'
        if self.bytes_out+len(line)>self.max_bytes:
            raise RuntimeError('TASK003 observer output budget exhausted; preserve partial trace')
        if self._file is None:
            self._file = self.path.open('x',encoding='ascii',newline='\n',buffering=1)
        self._file.write(line)
        self.bytes_out += len(line)
        self.io_ns_total += perf_counter_ns()-started_io
        self.capture_ns_total += captured
        self.copy_ns_total += self.copy_ns
        self.copy_ns = 0

    def context(self,stage,step=None):
        self.stage,self.current_step = stage,step

    def slots(self,video,a,b):
        ids = [rgb(x) for x in self.array(video.timestamp[a:b])]
        poses = self.array(video.poses[a:b])
        return [dict(slot=a+i,rgb_id=rid,pool='FILLER_TEMP' if self.filler_n is not None and a+i>=self.filler_n
                     else 'KEYFRAME_CACHE',w2c_xyzw=poses[i].tolist()) for i,rid in enumerate(ids)]

    def start_tracking(self,video):
        now = perf_counter_ns()
        tr = video.cfg['tracking']
        if (tr['frontend']['enable_online_ba'] or tr['frontend']['enable_loop'] or
                video.cfg['mapping']['enable'] or not video.cfg['droidvis'] or
                video.enable_bidirectional_uncer):
            raise RuntimeError('Task 003 effective flags differ from the sealed contract')
        self.emit('tracking_start',now,enable_online_ba=tr['frontend']['enable_online_ba'],
                  enable_loop=tr['frontend']['enable_loop'],mapping_enabled=video.cfg['mapping']['enable'],
                  droidvis=video.cfg['droidvis'],backend_stride=video.down_scale)

    def input_frame(self,timestamp):
        self.frame_id = rgb(timestamp)
        self.added = False
        self.context('frontend_input')

    def motion_score(self,delta,threshold,forced):
        now = perf_counter_ns()
        score = np.linalg.norm(self.array(delta).astype(np.float32),axis=-1).mean()
        self.emit('motion_filter_score',now,native_decision_proxy='CPU_NORM_OF_EXISTING_DELTA',
                  score=score,threshold=threshold,forced=bool(forced))

    def inserted(self,video,depth,source):
        now = perf_counter_ns()
        self.added = True
        i = video.counter.value-1
        row = self.slots(video,i,i+1)[0]
        depth_state = stats(self.array(depth))
        prior = stats(self.array(video.mono_disps[i]))
        disparity = stats(self.array(video.disps[i]))
        self.emit('keyframe_candidate_inserted',now,pose_init=source,row=row,disparity=disparity,
                  predicted_depth=depth_state,native_mono_prior=prior)

    def decision(self,video,start_count,init):
        now = perf_counter_ns()
        n = video.counter.value
        row = self.slots(video,n-1,n)[0] if n>start_count else None
        if row is None or row['rgb_id']!=self.frame_id:
            outcome = 'LOCAL_BA_REJECTED' if self.added else 'MOTION_FILTER_REJECTED'
        else:
            outcome = 'RETAINED' if init else 'RETAINED_WARMUP_PENDING'
        self.emit('keyframe_decision',now,outcome=outcome,local_initialized=bool(init),
                  before_count=start_count,after_count=n,row=row)

    def distance(self,video,d,threshold):
        now = perf_counter_ns()
        n=video.counter.value
        self.emit('frontend_distance',now,score=self.array(d).reshape(-1)[0],threshold=threshold,
                  rows=self.slots(video,n-2,n))

    def boundary(self,stage,video):
        now = perf_counter_ns()
        self.context(stage)
        if stage in ('final_pre','filler_anchors'):
            self.frame_id = None
        self.emit('stage_boundary',now,rows=self.slots(video,0,video.counter.value),
                  metric_depth_configured=bool(video.metric_depth_reg))

    def ba_before(self,video,target,weight,eta,ii,jj,t0,t1,iters,lm,ep,lr,weight_decay,motion_only,update_u,use_u,*,metric_selected,local_phase):
        now = perf_counter_ns()
        n = video.counter.value
        ir,jr = self.array(ii),self.array(jj)
        if not (0 <= t0 <= t1 <= n and len(ir)==len(jr) and
                np.all((ir>=0)&(ir<n)&(jr>=0)&(jr<n))):
            raise ValueError('inconsistent native BA window or slot graph')
        self.ba_id += 1
        rows = self.slots(video,0,n)
        ids = [row['rgb_id'] for row in rows]
        sample = sample_edges(ir,jr,ids)
        h = video.cfg['tracking']['uncertainty_params']
        # Only the decimated 24-edge sample is materialized. CPU copies seek the current stream state.
        def obs(value):
            return self.array(value[:,:,::GRID_STEP,::GRID_STEP][sample]).transpose(0,2,3,1) if sample else None
        data = dict(indices=(ir[sample],jr[sample]),target=obs(target),weight=obs(weight),
                    k=self.array(video.intrinsics[0]).copy(),use_u=bool(use_u),
                    target_u=bool(video.enable_bidirectional_uncer),n=n)
        self.before = data
        kx = np.union1d(np.arange(t0,t1),ir)
        used = bool(metric_selected and not motion_only and h['gamma_depth']!=0)
        # Native support is a strict disparity > 0 mask for the selected depth slots.
        prior_all = self.array(video.mono_disps[:n]) if not motion_only else None
        counts = [{'slot':int(i),'rgb_id':ids[i],'positive_mask_count':int((prior_all[i]>0).sum()),
                   'total':int(prior_all[i].size)} for i in kx] if not motion_only else []
        self.emit('ba_before',now,ba_id=self.ba_id,t0=t0,t1=t1,native_iterations_requested=iters,lm=lm,ep=ep,
                  lr=lr,weight_decay=weight_decay,motion_only=bool(motion_only),
                  source_uba=bool(use_u),target_uba=bool(use_u and video.enable_bidirectional_uncer),update_u=bool(update_u),
                  gamma_depth=h['gamma_depth'],gamma_data=h['gamma_data'],gamma_prior=h['gamma_prior'],
                  affine_u=bool(video.enable_affine_transform),
                  metric_depth_configured=bool(video.metric_depth_reg),metric_depth_branch_active=used,
                  metric_depth_prior_selected=bool(metric_selected),task004_local_phase=local_phase,
                  metric_depth_window_samples=int(len(kx)*video.mono_disps.shape[-2]*video.mono_disps.shape[-1]),
                  metric_depth_positive_support=sum(row['positive_mask_count'] for row in counts) if used else 0,
                  prior_support=counts if used else [],cached_prior_support=counts,
                  cached_prior_positive_support=sum(row['positive_mask_count'] for row in counts),
                  cached_prior_total=sum(row['total'] for row in counts),
                  backend_k=data['k'],eta_sample=stats(self.array(eta[::GRID_STEP,::GRID_STEP,::GRID_STEP])),
                  edge_slots=np.column_stack((ir,jr)),sample_edge_indices=sample,rows=rows,
                  **self.ba_numeric(video,data))

    def ba_numeric(self,video,data):
        n=data['n']
        d = self.array(video.disps[:n,::GRID_STEP,::GRID_STEP])
        u = self.array(video.uncertainties[:n,::GRID_STEP,::GRID_STEP])
        if data['target'] is None:
            geom = None
        else:
            geom = geometry(data['k'],self.array(video.poses[:n]),d,u,*data['indices'],
                            data['target'],data['weight'],data['use_u'],data['target_u'])
        return dict(sample_grid_step=GRID_STEP,disparity=stats(d),positive_depth=depth_from_disp(d),uncertainty=stats(u),geometry=geom)

    def ba_after(self,video,clamped=False):
        now = perf_counter_ns()
        data = self.before
        # Count all active slots at the native return and immediately after Python clamp.
        full = self.array(video.disps[:data['n']])
        grid = dict(scope='ALL_PIXELS_ACTIVE_SLOT_PREFIX', active_slots=data['n'],
                    total=int(full.size), negative=int((np.isfinite(full) & (full < 0)).sum()),
                    nonfinite=int((~np.isfinite(full)).sum()),
                    float32_floor_count=int((full == np.float32(1e-5)).sum()))
        if clamped:
            d = full[:,::GRID_STEP,::GRID_STEP]
            self.emit('ba_after_clamp',now,ba_id=self.ba_id,disparity=stats(d),full_disparity_grid=grid,
                      float32_floor_count=int((d==np.float32(1e-5)).sum()))
            self.before = {}
        else:
            self.emit('ba_after_native',now,ba_id=self.ba_id,rows=self.slots(video,0,data['n']),full_disparity_grid=grid,
                      **self.ba_numeric(video,data))

    def filler_begin(self,video,n,m,t0,t1):
        now = perf_counter_ns()
        self.batch += 1
        self.filler_n=n
        self.context('filler_interpolated')
        low,high=self.array(t0).tolist(),self.array(t1).tolist()
        anchors=self.slots(video,0,n)
        self.emit('filler_interpolated',now,rows=self.slots(video,n,n+m),
                  bracket_rows=[[anchors[i],anchors[j]] for i,j in zip(low,high)])

    def filler_step(self,video,n,m,step):
        now=perf_counter_ns()
        self.emit('filler_pose_update',now,update_number=step+1,rows=self.slots(video,n,n+m),ba_id=self.ba_id)

    def filler_end(self,video,n,m):
        now=perf_counter_ns()
        self.emit('filler_batch_result',now,rows=self.slots(video,n,n+m))
        self.filler_n=None

    def export(self,c2w,kf_timestamps):
        now=perf_counter_ns()
        if tuple(c2w.shape)!=(487,4,4):
            raise ValueError('unexpected final export dimensions')
        self.context('export_matrix_after_anchor_reinsertion')
        self.emit('export_matrix',now,c2w=c2w,rgb_ids=list(range(1,488)),anchor_rgb_ids=[rgb(t) for t in kf_timestamps])
        self.emit('observer_overhead',perf_counter_ns(),events_before_summary=self.ord,
                  bytes_before_summary=self.bytes_out,capture_and_summary_ns_total=self.capture_ns_total,
                  copy_to_cpu_ns_total=self.copy_ns_total,encode_and_write_ns_total=self.io_ns_total)


_recorder = None


def recorder():
    global _recorder
    if _recorder is None:
        _recorder = Recorder(Path(os.environ['GAMECAM_TASK003_OBSERVER_JSONL']))
    return _recorder
