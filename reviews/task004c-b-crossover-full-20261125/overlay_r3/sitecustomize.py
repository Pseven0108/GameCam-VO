"""Fail-closed installation of the attempt-output compatibility overlay."""
import os,pathlib,sys
root=pathlib.Path(__file__).resolve().parent
if os.environ.get('GAMECAM_IO_OVERLAY')=='1':
    try:
        sys.path.insert(0,str(root/'overlay'))
        from io_import_overlay import install
        install(root)
    except BaseException:
        import traceback
        traceback.print_exc()
        os._exit(73)
