"""Generate a narrowly adapted TASK009 local runner, retaining its native solver."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OLD=Path('D:/aaa/GameCam-VO-TASK009')
source=(OLD/'experiments/TASK009/scripts/run_droid_window.py').read_text()
source=source.replace("SOURCE = ROOT / 'external/DROID-W'", "SOURCE = Path('/mnt/d/aaa/GameCam-VO-TASK009/external/DROID-W')")
source=source.replace("    p.add_argument('--priors', type=Path, required=True)",
    "    p.add_argument('--dataset', required=True)\n    p.add_argument('--method', default='baseline', choices=['baseline','legacy','legacy_mean','neutral','gmos','geomotion','geometry','fusion','static','fusion_static','depth','depth_static','depth_fusion'])\n    p.add_argument('--seed', type=int, default=43)\n    p.add_argument('--priors', type=Path, required=True)")
source=source.replace("    a = p.parse_args()", "    a = p.parse_args()\n    datasets=json.loads((ROOT/'experiments/TASK010-A/private/DATA_MANIFEST.json').read_text())\n    dataset=next(d for d in datasets if d['name']==a.dataset)\n    global RGB\n    RGB=Path(dataset['rgb_dir'].replace('D:', '/mnt/d').replace(chr(92), '/'))\n    global IMAGE_SUFFIX\n    IMAGE_SUFFIX=dataset.get('image_suffix','.jpg')")
source=source.replace("f'{self.ids[i]:05d}.jpg'", "(f'{self.ids[i]:05d}'+IMAGE_SUFFIX)")
source=source.replace("'seed': 43", "'seed': a.seed, 'dataset':a.dataset,'method':a.method")
source=source.replace('torch.manual_seed(43)','torch.manual_seed(a.seed)').replace('torch.cuda.manual_seed_all(43)','torch.cuda.manual_seed_all(a.seed)').replace('np.random.seed(43)','np.random.seed(a.seed)').replace('random.seed(43)','random.seed(a.seed)')
start=source.index("        with np.load(a.priors / 'offline_gt.npz'")
stop=source.index("        cfg = yaml.safe_load",start)
source=source[:start]+"        k_all=np.load(RGB.parent/'intrinsics.npy',allow_pickle=False)\n        k=k_all[0].copy()\n        if np.max(np.abs(k_all-k))>.001:raise RuntimeError('Variable K not admitted')\n"+source[stop:]
source=source.replace("        from gamecam.modules.dynamic_prior.observation import install_ba_observer\n        ba_calls=install_ba_observer(video,dict(enumerate(ids)),a.output/'native_ba_observations')", "        from task010_fusion import install_observer, install_fusion\n        ba_calls=install_observer(video,dict(enumerate(ids)),a.output/'native_ba_observations')")
needle='        static_calls=[]'
source=source.replace(needle,"        if a.method not in ('baseline','static','depth','depth_static'):\n            gate_method='fusion' if a.method=='depth_fusion' else a.method\n            gate_calls=install_fusion(video,dataset,gate_method,a.output/'dynamic_fusion.jsonl')\n"+needle)
source=source.replace("'32-frame local window RGB301..332'", "'32-frame local exploratory dataset '+a.dataset")
source=source.replace("cfg.update(scene='night007',", "cfg['setup_seed']=a.seed\n        cfg.update(scene=a.dataset,")
source=source.replace("ROOT/'gamecam/modules/motion_decomposition/droid_adapter.py']", "ROOT/'gamecam/modules/motion_decomposition/droid_adapter.py', ROOT/'experiments/TASK010-A/scripts/task010_fusion.py']")
source=source.replace("'native_u_enabled':True", "'native_u_enabled':True")
source=source.replace("                frontend(force, writer)","                video._task010_phase='FRONTEND_LOCAL_BA' if frontend.is_initialized else 'INITIALIZATION'\n                frontend(force, writer)")
source=source.replace("            backend = Backend(net, video, cfg)","            video._task010_phase='FINAL_GLOBAL_BA'\n            backend = Backend(net, video, cfg)")
source=source.replace("            filler = PoseTrajectoryFiller", "            video._task010_phase='TRAJECTORY_FILLER'\n            filler = PoseTrajectoryFiller")
dest=ROOT/'experiments/TASK010-A/scripts/run_window.py'
dest.write_text(source,encoding='utf-8')
script='''#!/bin/sh
set -eu
ROOT=/mnt/d/aaa/GameCam-VO-TASK010-A
RUNTIME=/mnt/d/aaa/GameCam-VO-TASK009/runtime
export TMPDIR=/mnt/d/aaa/tmp/gamecam-vo
export CUDA_HOME="$RUNTIME/cuda128"
export PATH="$RUNTIME/wsl310/bin:$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/targets/x86_64-linux/lib:${LD_LIBRARY_PATH:-}"
export TORCH_HOME=/mnt/d/aaa/caches/torch
export HF_HOME=/mnt/d/aaa/caches/huggingface
export XDG_CACHE_HOME=/mnt/d/aaa/caches/task010a
export MPLCONFIGDIR=/mnt/d/aaa/caches/task010a/matplotlib
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX=/mnt/d/aaa/caches/task010a/wsl_pycache
export PYTHONPATH="$ROOT:$ROOT/experiments/TASK010-A/scripts:/mnt/d/aaa/GameCam-VO-TASK009/external/DROID-W:/mnt/d/aaa/GameCam-VO-TASK009/external/DROID-W/thirdparty/lietorch:${PYTHONPATH:-}"
mkdir -p "$TMPDIR" "$MPLCONFIGDIR"
cd "$ROOT"
exec python -B "$@"
'''
(dest.parent/'run_native.sh').write_text(script,encoding='utf-8',newline='\n')
