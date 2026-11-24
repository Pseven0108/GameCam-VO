"""Explicit RNG/flag state; no CUDA initialization for capture or restore."""
import random
import numpy as np
import torch
from control_common import ControlError

def capture_rng_state():
    n=np.random.get_state()
    return {'python':random.getstate(),'numpy':{'algorithm':n[0],'keys':n[1].tolist(),'pos':n[2],'has_gauss':n[3],'cached_gaussian':n[4]},
        'torch_cpu':torch.get_rng_state().clone(),'cuda_initialized':torch.cuda.is_initialized(),
        'cuda_states':torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else [],
        'flags':{'cudnn_deterministic':torch.backends.cudnn.deterministic,'cudnn_benchmark':torch.backends.cudnn.benchmark,
            'cudnn_allow_tf32':torch.backends.cudnn.allow_tf32,'matmul_allow_tf32':torch.backends.cuda.matmul.allow_tf32,
            'deterministic_algorithms':torch.are_deterministic_algorithms_enabled(),
            'deterministic_warn_only':torch.is_deterministic_algorithms_warn_only_enabled(),
            'grad_enabled':torch.is_grad_enabled(),'autocast_enabled':torch.is_autocast_enabled(),
            'autocast_cpu_enabled':torch.is_autocast_cpu_enabled()}}

def restore_rng_state(s):
    if s['cuda_initialized']!=torch.cuda.is_initialized():raise ControlError('CUDA lifecycle mismatch; never initialize CUDA to restore')
    flags=capture_rng_state()['flags']
    if flags!=s['flags']:raise ControlError('Runtime math/context flag mismatch; implicit changes forbidden')
    n=s['numpy'];random.setstate(s['python']);np.random.set_state((n['algorithm'],np.array(n['keys'],dtype=np.uint32),n['pos'],n['has_gauss'],n['cached_gaussian']))
    torch.set_rng_state(s['torch_cpu'])
    if s['cuda_initialized']:torch.cuda.set_rng_state_all(s['cuda_states'])
