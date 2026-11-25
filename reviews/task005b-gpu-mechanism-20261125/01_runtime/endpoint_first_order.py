import pathlib,hashlib,base64
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1');p=r/'tools/replay_state.py';raw=p.read_bytes();old=b"{'A':(1,1),'B':(1,0),'C':(0,1),'D':(0,0)}.items()";new=b"{'A':(1,1),'D':(0,0),'B':(1,0),'C':(0,1)}.items()"
assert raw.count(old)==1 and not any((r/'results').iterdir());p.write_bytes(raw.replace(old,new));print('endpoint_cells_first_before_crossed_cells')
