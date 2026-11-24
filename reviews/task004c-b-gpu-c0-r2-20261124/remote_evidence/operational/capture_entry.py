"""Single-mode entry preserving the official pre-construction spawn setup."""
import multiprocessing as mp
import os

if __name__ == '__main__':
    if os.environ.get('GAMECAM_NATIVE_APPROVED_MODE') != 'capture':
        raise SystemExit('ONLY_C0_CAPTURE_AUTHORIZED')
    # The official run.py sets spawn before constructing SLAM/DepthVideo.
    # Calling the reviewed CLI as an imported module otherwise misses that line.
    mp.set_start_method('spawn', force=True)
    from runner.run_native_smoke import main
    raise SystemExit(main())
