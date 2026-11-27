"""Runtime dispatcher audit of explicit Tensor D2H copies and scalar reads.

Pairs with source review; not a claim about every driver-internal PCIe byte.
An independent profiler trace is requested by the CUDA test harness as well.
"""
import torch
from torch.utils._python_dispatch import TorchDispatchMode

class TransferAudit(TorchDispatchMode):
    def __init__(self):
        super().__init__();self.transfers=[];self.scalar_reads=[]
    def __torch_dispatch__(self,func,types,args=(),kwargs=None):
        kwargs=kwargs or {}
        if str(func)=='aten._to_copy.default' and args and torch.is_tensor(args[0]):
            source=args[0];target=kwargs.get('device',source.device)
            if source.device.type=='cuda' and torch.device(target).type=='cpu':
                self.transfers.append(dict(op=str(func),shape=list(source.shape),dtype=str(source.dtype),
                    bytes=source.numel()*source.element_size(),destination='cpu'))
        if str(func)=='aten._local_scalar_dense.default' and args[0].device.type=='cuda':
            self.scalar_reads.append(dict(op=str(func),shape=list(args[0].shape),bytes=args[0].element_size()))
        return func(*args,**kwargs)
    def report(self):
        return dict(transfers=self.transfers,explicit_D2H_bytes=sum(r['bytes'] for r in self.transfers),
            CUDA_scalar_reads=self.scalar_reads,
            full_buffer_pixel_D2H=any(len(r['shape'])==3 for r in self.transfers),
            coverage='Tensor copy-to-CPU operators and CUDA scalar reads in audited Python call; driver-internal traffic separate')
