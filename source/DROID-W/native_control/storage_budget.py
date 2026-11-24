"""Exact serialized byte accounting plus explicit filesystem safety reserves."""
import hashlib,math,os,pathlib,shutil
from control_common import ControlError

class CountingHashWriter:
    def __init__(self):self.bytes=0;self.hash=hashlib.sha256();self.closed=False
    def write(self,data):
        if self.closed:raise ValueError('Closed counting writer')
        view=memoryview(data);self.bytes+=len(view);self.hash.update(view);return len(view)
    def flush(self):pass
    def tell(self):return self.bytes
    def writable(self):return True

def round_bytes(size,block):return ((size+block-1)//block)*block

def make_budget(files,manifest_bytes,complete_bytes,*,block_size=4096,
                floor_bytes=10*1024**3,retained_scratch_bytes=512*1024**2,metadata_reserve_bytes=16*1024**2):
    values=[row['bytes'] for row in files.values()]+[manifest_bytes,complete_bytes]
    if any(type(x) is not int or x<0 for x in values) or block_size<=0:raise ControlError('Invalid storage budget')
    logical=sum(values);rounded=sum(round_bytes(x,block_size) for x in values)
    return {'schema':'GAMECAM_EXACT_SERIALIZED_BUDGET_V1','serialized_tensor_files_bytes':sum(row['bytes'] for row in files.values()),
            'manifest_bytes':manifest_bytes,'complete_bytes':complete_bytes,'exact_checkpoint_logical_bytes':logical,
            'file_count':len(values),'filesystem_block_bytes':block_size,'rounded_file_data_reservation_bytes':rounded,
            'filesystem_metadata_reserve_bytes':metadata_reserve_bytes,'retained_scratch_reserve_bytes':retained_scratch_bytes,
            'safety_floor_bytes':floor_bytes,'minimum_free_before_save_bytes':rounded+metadata_reserve_bytes+retained_scratch_bytes+floor_bytes,
            'physical_filesystem_overhead_is_exact':False,'logical_serialization_bytes_are_exact':True}

def check_budget(path,budget,*,remaining_files=None,free_bytes=None):
    p=pathlib.Path(path)
    while not p.exists():p=p.parent
    free=shutil.disk_usage(p).free if free_bytes is None else free_bytes
    remaining=budget['rounded_file_data_reservation_bytes'] if remaining_files is None else sum(round_bytes(x,budget['filesystem_block_bytes']) for x in remaining_files)
    required=remaining+budget['filesystem_metadata_reserve_bytes']+budget['retained_scratch_reserve_bytes']+budget['safety_floor_bytes']
    if free<required:raise ControlError('STORAGE_BLOCKED: exact remaining checkpoint reservation=%d free=%d'%(required,free))
    return {'free_bytes':free,'required_free_bytes':required,'remaining_file_reservation_bytes':remaining}

def block_size(path):
    p=pathlib.Path(path)
    while not p.exists():p=p.parent
    return os.statvfs(p).f_frsize
