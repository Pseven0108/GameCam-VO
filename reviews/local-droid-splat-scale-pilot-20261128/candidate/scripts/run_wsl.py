"""Start only local WSL jobs with all new outputs and caches on D:."""
import os,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
E='/home/lsuser/.local/share/gamecam-vo/envs/droid-w'
L='/mnt/d/aaa/GameCam-VO-DROID-SPLAT-CANDIDATE'
def main():
    if len(sys.argv)<2:raise SystemExit('Specify script basename')
    script=sys.argv[1]
    target=L+'/candidate/scripts/'+script
    if script.startswith('test_'):target=L+'/candidate/tests/'+script
    command=['wsl','-u','lsuser','--','/usr/bin/env',
        f'PATH={E}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
        f'LD_LIBRARY_PATH={E}/lib:{E}/lib/python3.10/site-packages/torch/lib',
        f'CUDA_HOME={E}','TORCH_CUDA_ARCH_LIST=12.0','MAX_JOBS=1',
        f'TMPDIR={L}/toolchain/tmp',f'XDG_CACHE_HOME={L}/toolchain/cache',
        f'TORCH_EXTENSIONS_DIR={L}/toolchain/build','OMP_NUM_THREADS=4',
        'PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True',
        E+'/bin/python3.10',target,*sys.argv[2:]]
    for d in ['tmp','cache','build']:(ROOT/'toolchain'/d).mkdir(parents=True,exist_ok=True)
    raise SystemExit(subprocess.call(command))
if __name__=='__main__':main()
