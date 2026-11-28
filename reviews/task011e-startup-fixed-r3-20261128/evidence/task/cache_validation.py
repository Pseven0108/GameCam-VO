import json
from common import TASK,sha

def validate_cache(window):
    root=TASK/'cache'/window;p=root/'CACHE_RECEIPT.json'
    if not p.is_file():raise RuntimeError('UNFINISHED_CACHE_ATTEMPT: '+window)
    m=json.loads(p.read_text())
    if not(m['status']=='COMPLETE' and m['frames']==64 and m['model_forwards']==128 and m['native_forward_RNG_unchanged']
           and m['precision_protocol']=='NATIVE_MOTION_FILTER_AUTOCAST_V2' and m['autocast_enabled']
           and m['autocast_dtype']=='torch.float16' and m['input_preprocess_device']=='cpu'):
        raise RuntimeError('Cache precision/RNG contract mismatch')
    if [r['timestamp'] for r in m['records']]!=list(range(64)):raise RuntimeError('Cache incomplete')
    for r in m['records']:
        q=root/f"{r['timestamp']:05d}.npz"
        if q.stat().st_size!=r['bytes'] or sha(q)!=r['sha256']:raise RuntimeError('Cache SHA mismatch')
    return dict(window=window,status='COMPLETE',frames=64,model_forwards=128,
                bytes=sum(r['bytes'] for r in m['records']),receipt_sha256=sha(p),seconds=m['seconds'])
