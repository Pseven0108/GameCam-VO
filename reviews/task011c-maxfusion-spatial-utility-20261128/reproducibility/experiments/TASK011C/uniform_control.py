"""A7 changes only the spatial distribution of A5's native BA-grid prior.

No models or CUDA modules are imported here. A0/A1/A4/A5 are delegated to the
byte-locked TASK011B implementation, never reimplemented. CPU tests exercise
the runtime adapter with CPU torch tensors; no GPU equivalence is asserted.
"""
from dataclasses import asdict, dataclass
from functools import lru_cache, wraps
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

TASK = Path(__file__).resolve().parent
FORMAL_ARMS = ('A0', 'A1', 'A4', 'A5', 'A7')
MEAN_ATOL = 1e-6


@lru_cache(maxsize=1)
def frozen():
    lock = json.loads((TASK / 'configs/FROZEN_SOURCE_LOCK.json').read_text())
    root = TASK.parent / 'TASK011B'
    for record in lock['controller_dependencies']:
        path = root / record['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            raise RuntimeError('Frozen TASK011B controller dependency changed: ' + record['path'])
    path = root / 'CADP_DR_EXPERIMENTAL_BRANCH/controller.py'
    spec = importlib.util.spec_from_file_location('task011c_frozen_task011b_controller', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class UniformConfig:
    arm: str = 'A7'
    CADP_DR_ENABLE: bool = True
    DEPTH_RELIABILITY_METHOD: str = 'UniformFromValidityAwareMax'
    TTA_VALIDITY_ENABLE: bool = True
    GEOMETRY_NEED_ENABLE: bool = False
    DEPTH_PRIOR_ALPHA: float = .01
    RELIABILITY_FUSION_WEIGHT: float = .5
    DEPTH_MIN_NATIVE_UNITS: float = 1e-6
    DISAGREEMENT_EPSILON: float = 1e-6

    def validate(self):
        if asdict(self) != asdict(UniformConfig()):
            raise ValueError('A7 protocol cannot be retuned or relabelled')
        return self


def arm_config(arm):
    if arm not in FORMAL_ARMS:
        raise ValueError('Arm outside TASK011C five-arm protocol')
    return UniformConfig().validate() if arm == 'A7' else frozen().arm_config(arm)


def coefficient_map(native, flip_aligned, confidence, tta_valid, config):
    """A7 returns the unchanged A5 cache; uniformization MUST wait for BA.

    A full-image mean or a precomputed per-image scalar would miss the actual
    45x80 sampling grid, source indices and native prior mask.
    """
    config.validate()
    base = frozen().arm_config('A5') if config.arm == 'A7' else config
    values, receipt = frozen().coefficient_map(native, flip_aligned, confidence, tta_valid, base)
    if config.arm == 'A7':
        receipt.update(cache_is_exact_A5=True, uniformization_deferred_until_actual_BA=True)
    return values, receipt


def source_indices(ii, t0, t1, live_frames):
    """Exactly the native sorted unique union: arange(t0,t1) union ii."""
    values = np.asarray(ii)
    if values.ndim != 1 or values.dtype.kind not in 'iu':
        raise ValueError('Native ii must be a one-dimensional integer array')
    if any(isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, np.integer)) for v in (t0, t1, live_frames)):
        raise ValueError('Native source bounds must be integers')
    if not 0 <= t0 < t1 <= live_frames:
        raise ValueError('Native BA bounds exceed live keyframes')
    if values.size and (np.any(values < 0) or np.any(values >= live_frames)):
        raise ValueError('Native graph source refers to a missing keyframe')
    return np.unique(np.concatenate((np.arange(t0, t1, dtype=np.int64), values.astype(np.int64))))


def timestamp_slots(timestamps, cache_keys):
    values = np.asarray(timestamps)
    if values.ndim != 1 or not np.isfinite(values).all() or np.any(values != np.floor(values)):
        raise ValueError('Keyframe timestamps must be exact finite input indices')
    ids = values.astype(np.int64)
    if len(set(ids)) != len(ids) or np.any(ids < 0) or any(int(v) not in cache_keys for v in ids):
        raise ValueError('Duplicate or unmapped keyframe timestamp')
    return ids


def _check_arrays(a5, native_valid, mono, indices):
    if a5.ndim != 3 or a5.shape != native_valid.shape or a5.shape != mono.shape:
        raise ValueError('Full native BA grids must have matching [buffer,H,W] shapes')
    if a5.dtype != np.float32 or native_valid.dtype != bool or mono.dtype != np.float32:
        raise ValueError('FP32 coefficients/mono and exact boolean validity required')
    if indices.ndim != 1 or indices.dtype.kind not in 'iu' or len(indices) == 0:
        raise ValueError('Nonempty unique native integer source indices required')
    if len(np.unique(indices)) != len(indices) or indices.min() < 0 or indices.max() >= len(a5):
        raise ValueError('Duplicate or out-of-bounds source index')
    selected = a5[indices]
    if not np.isfinite(selected).all() or np.any((selected < 0) | (selected > 1)):
        raise ValueError('A5 coefficients must be finite and bounded')
    if not np.isfinite(mono[indices]).all():
        raise ValueError('Nonfinite native mono disparity cannot be silently repaired')
    if np.any(selected[~native_valid[indices]] != 0):
        raise ValueError('A5 unexpectedly enables an invalid native depth')


def _receipt(reference, actual, mask, indices):
    """Independent float64 audit of actual FP32 coefficient fields."""
    rows = []
    for slot in indices:
        m = mask[slot]
        count = int(m.sum())
        a = reference[slot][m].astype(np.float64)
        b = actual[slot][m].astype(np.float64)
        mean_a = float(a.mean()) if count else None
        mean_b = float(b.mean()) if count else None
        delta = abs(mean_a - mean_b) if count else 0.
        if delta > MEAN_ATOL or (count and not np.all(b == b[0])):
            raise RuntimeError('A5/A7 mean matching or A7 uniformity failed')
        if not np.array_equal(reference[slot] > 0, actual[slot] > 0):
            raise RuntimeError('Positive prior support changed')
        rows.append(dict(source_slot=int(slot),eligible_pixels=count,
                         A5_mean=mean_a,A7_mean=mean_b,absolute_mean_difference=delta,
                         A5_spatial_sd=float(a.std()) if count else None,
                         A7_spatial_sd=float(b.std()) if count else None,
                         empty_support=count == 0,eligible_and_positive_support_equal=True))
    a = reference[indices].astype(np.float64)
    b = actual[indices].astype(np.float64)
    eligible = int(mask[indices].sum())
    eligible_delta = abs(float(a.sum() - b.sum()) / eligible) if eligible else 0.
    dense_delta = abs(float(a.mean() - b.mean()))
    if eligible_delta > MEAN_ATOL or dense_delta > MEAN_ATOL:
        raise RuntimeError('Actual-call effective mean mismatch')
    return dict(status='PASS_SAME_STATE_COEFFICIENT_CONTRACT',frames=rows,
                eligible_pixels=eligible,total_source_pixels=int(a.size),
                eligible_mean_difference=eligible_delta,dense_mean_difference=dense_delta,
                effective_alpha_mean_difference=.01 * dense_delta,absolute_tolerance=MEAN_ATOL,
                matched_against='Counterfactual A5 on THIS exact BA input',
                cross_run_equal_means_not_asserted=True)


def uniform_for_call(a5, native_valid, mono, indices):
    """CPU FP32 reference, including the actual native prior mask."""
    a5, native_valid, mono, indices = map(np.asarray, (a5, native_valid, mono, indices))
    _check_arrays(a5, native_valid, mono, indices)
    mask = native_valid & (mono > 0)
    reference = np.zeros_like(a5)
    actual = np.zeros_like(a5)
    for slot in indices:
        m = mask[slot]
        if np.any(m & (a5[slot] <= 0)):
            raise ValueError('Zero A5 strength within M: uniformization would change positive support; STOP')
        reference[slot][m] = a5[slot][m]
        if m.any():
            actual[slot][m] = a5[slot][m].mean(dtype=np.float32)
    return actual, _receipt(reference, actual, mask, indices)


def torch_uniform_for_call(a5, native_valid, mono, indices):
    """Device-preserving adapter; CPU tests do not certify GPU reductions.

    No native tensor is changed. Only the appended candidate prior-strength
    argument is newly allocated. Logging transfers are bounded to source grids.
    """
    import torch
    if a5.dtype != torch.float32 or mono.dtype != torch.float32 or native_valid.dtype != torch.bool:
        raise ValueError('Native FP32/boolean tensor contract changed')
    if not (a5.device == mono.device == native_valid.device == indices.device):
        raise ValueError('Source inputs must remain on the same native device')
    if indices.dtype != torch.long:
        raise ValueError('Native source indices must be torch.long')
    # Use the same validation as the independent CPU reference, without relying
    # on CPU means to choose the actual device coefficient.
    ix = indices.detach().cpu().numpy()
    a = a5.detach().cpu().numpy()
    nv = native_valid.detach().cpu().numpy()
    d = mono.detach().cpu().numpy()
    _check_arrays(a, nv, d, ix)
    mask = native_valid & (mono > 0)
    actual = torch.zeros_like(a5)
    for slot in ix:
        m = mask[int(slot)]
        if torch.any(m & (a5[int(slot)] <= 0)).item():
            raise ValueError('Zero A5 strength within M would change positive support; STOP')
        if m.any().item():
            actual[int(slot)][m] = a5[int(slot)][m].mean(dtype=torch.float32)
    reference = np.zeros_like(a)
    for slot in ix:
        m = nv[slot] & (d[slot] > 0)
        reference[slot][m] = a[slot][m]
    proof = _receipt(reference, actual.detach().cpu().numpy(), nv & (d > 0), ix)
    proof.update(compute_device=str(a5.device),reduction_dtype='torch.float32',
                 CUDA_equivalence='UNVERIFIED' if a5.device.type == 'cpu' else 'ACTUAL_CALL_MEAN_CHECK_ONLY')
    return actual, proof


def install(video, candidate, config, reliability_by_timestamp, output,
            regression_callback=None, native_valid_by_timestamp=None):
    """Keep previous arms identical; A7 alone adds an actual-call adapter."""
    config.validate()
    if config.arm != 'A7':
        return frozen().install(video,candidate,config,reliability_by_timestamp,output,regression_callback)
    if hasattr(video, '_task011b_installed') or hasattr(video, '_task011c_installed'):
        raise RuntimeError('Do not stack controllers')
    if native_valid_by_timestamp is None or set(native_valid_by_timestamp) != set(reliability_by_timestamp):
        raise ValueError('A7 needs explicit native-valid maps for every cached A5 field')
    if set(reliability_by_timestamp) != set(range(64)):
        raise ValueError('A7 needs all 64 original window-relative input indices')
    import torch
    output = Path(output)
    if output.exists():
        raise FileExistsError('Preserve previous BA receipts')
    output.parent.mkdir(parents=True, exist_ok=True)
    fields, valids = {}, {}
    for timestamp, value in reliability_by_timestamp.items():
        value = np.asarray(value)
        valid = np.asarray(native_valid_by_timestamp[timestamp])
        if value.shape != (video.ht, video.wd) or valid.shape != value.shape or valid.dtype != bool:
            raise ValueError('Full-resolution A5/validity grids disagree with the tracker')
        if not np.isfinite(value).all() or np.any((value < 0) | (value > 1)) or np.any(value[~valid] != 0):
            raise ValueError('Invalid A5 cache')
        sampled = value[video.slice_h, video.slice_w]
        if sampled.shape != tuple(video.disps.shape[-2:]):
            raise ValueError('Native BA sampling grid changed')
        fields[timestamp] = torch.as_tensor(sampled.copy(),dtype=torch.float32,device=video.device)
        valids[timestamp] = torch.as_tensor(valid[video.slice_h, video.slice_w].copy(),dtype=torch.bool,device=video.device)
    original = video.ba
    namespace = original.__func__.__globals__
    native_backend = namespace['droid_backends']
    calls = 0

    class Proxy:
        def __getattr__(self, name):
            return getattr(native_backend, name)

        def ba(self, *args):
            nonlocal calls
            if len(args) != 30:
                raise RuntimeError('Frozen native BA positional signature changed')
            if abs(float(args[20]) - .01) > 1e-12:
                raise RuntimeError('Frozen gamma_depth changed')
            phase = getattr(video, '_task011b_phase', None)
            active = frozen().should_intervene(frozen().arm_config('A5'),phase,bool(args[23]),video.metric_depth_reg)
            calls += 1
            receipt = dict(arm='A7',call=calls,phase=phase,intervention=active,
                           iterations=int(args[15]),gamma_depth=float(args[20]),
                           motion_only=bool(args[23]),enable_update_uncer=bool(args[25]),
                           enable_udba=bool(args[26]),native_positional_arguments_forwarded_unchanged=True)
            if active:
                live = int(video.counter.value)
                keys = timestamp_slots(video.timestamp[:live].detach().cpu().numpy(),fields)
                a5 = torch.zeros_like(video.disps)
                nv = torch.zeros_like(video.disps,dtype=torch.bool)
                for slot, key in enumerate(keys):
                    a5[slot] = fields[int(key)]
                    nv[slot] = valids[int(key)]
                ix = source_indices(args[11].detach().cpu().numpy(),int(args[13]),int(args[14]),live)
                indices = torch.as_tensor(ix,device=args[11].device,dtype=torch.long)
                strength, proof = torch_uniform_for_call(a5,nv,args[3],indices)
                receipt['uniform_matching'] = proof
                receipt['source_slots'] = ix.tolist()
                receipt['source_input_indices'] = keys[ix].tolist()
                result = candidate.ba(*args,strength.contiguous(),True,False)
                if len(result) != 3:
                    raise RuntimeError('Frozen candidate return signature changed')
            else:
                result = native_backend.ba(*args)
            with output.open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(receipt,allow_nan=False) + '\n')
            return result

    proxy = Proxy()

    @wraps(original)
    def wrapped(*args, **kwargs):
        if namespace['droid_backends'] is not native_backend:
            raise RuntimeError('Another BA interceptor is active')
        namespace['droid_backends'] = proxy
        try:
            return original(*args, **kwargs)
        finally:
            namespace['droid_backends'] = native_backend

    video.ba = wrapped
    video._task011c_installed = True
    return dict(config=asdict(config),scope=frozen().MAIN,
                native_extension_replaced=False,GPU_numerical_equivalence='UNVERIFIED')
