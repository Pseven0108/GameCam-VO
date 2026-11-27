"""Independent CPU experiment on synthetic BA grids, not VIPER results."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
import json
import time

import numpy as np
import torch

from common import TASK,csvwrite,dump
from uniform_control import source_indices,torch_uniform_for_call,uniform_for_call


def main():
    out = TASK/'cpu_probe_001'
    out.mkdir(exist_ok=False)
    torch.set_num_threads(2)
    rows = []
    maximum = 0.
    input_unchanged = True
    for seed in (43,44,45):
        rng = np.random.default_rng(seed)
        a5 = rng.uniform(1e-7,1,(12,45,80)).astype(np.float32)
        valid = rng.random(a5.shape)>.1
        a5[~valid] = 0
        for call in range(4):
            mono = (rng.random(a5.shape) > (.1+.15*call)).astype(np.float32)
            ii = rng.integers(0,12,14)
            ix = source_indices(ii,3,8,12)
            before = [x.copy() for x in (a5,valid,mono)]
            start = time.perf_counter()
            expected,_ = uniform_for_call(a5,valid,mono,ix)
            actual,proof = torch_uniform_for_call(torch.from_numpy(a5),torch.from_numpy(valid),
                                                torch.from_numpy(mono),torch.from_numpy(ix))
            seconds = time.perf_counter()-start
            np.testing.assert_allclose(actual.numpy(),expected,atol=1e-6,rtol=0)
            for x,y in zip(before,(a5,valid,mono)):
                input_unchanged &= bool(np.array_equal(x,y))
            for record in proof['frames']:
                rows.append(dict(seed=seed,synthetic_call=call,CPU_only=True,
                                 source='SYNTHETIC_NOT_VIPER',**record))
                maximum = max(maximum,record['absolute_mean_difference'])
            dump(out/f'seed{seed}_call{call}.json',dict(**proof,seconds=seconds,
                numpy_vs_torch_max_error=float(np.max(np.abs(expected-actual.numpy()))),
                source='SYNTHETIC_NOT_VIPER',GT_or_models_used=False))
    csvwrite(out/'SYNTHETIC_PER_SOURCE_MEAN_AUDIT.csv',rows)
    summary = dict(status='PASS',synthetic_calls=12,synthetic_source_rows=len(rows),
        maximum_FP32_mean_error=maximum,absolute_tolerance=1e-6,input_arrays_unchanged=input_unchanged,
        native_BA_grid_hw=[45,80],seeds=[43,44,45],CUDA_initialized=torch.cuda.is_initialized(),
        VIPER_algorithm_results=False,GPU_equivalence='NOT_TESTED')
    if not input_unchanged or summary['CUDA_initialized']:
        raise RuntimeError('CPU experiment violated input/device contract')
    dump(out/'SUMMARY.json',summary)
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
