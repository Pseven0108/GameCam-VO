import sys,unittest
from pathlib import Path
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from transfer_audit import TransferAudit
from uniform_control import gather_source_strength,previous,torch_uniform_for_call
import test_source_gather as source_fixture

class TransferContracts(unittest.TestCase):
    def test_runtime_adapter_only_copies_bounded_summary(self):
        if not torch.cuda.is_available():raise RuntimeError('CUDA audit cannot be skipped')
        v,args,c,n=source_fixture.SourceGather().fixture('cuda')
        with TransferAudit() as audit:out,proof=gather_source_strength(v,args,c,n)
        r=audit.report()
        self.assertFalse(r['full_buffer_pixel_D2H']);self.assertEqual(r['CUDA_scalar_reads'],[])
        self.assertEqual(len(r['transfers']),1)
        self.assertEqual(r['explicit_D2H_bytes'],(5+1)*14*8)
    def test_negative_control_detects_all_three_legacy_buffer_copies(self):
        a=torch.full((500,45,80),.4,device='cuda');nv=a.bool();dm=torch.ones_like(a);ix=torch.tensor([0,17],device='cuda')
        with TransferAudit() as audit:previous().torch_uniform_for_call(a,nv,dm,ix)
        copies=[r for r in audit.report()['transfers'] if r['shape']==[500,45,80]]
        # A5, validity and mono inputs, plus the legacy full output audit.
        self.assertEqual(len(copies),4)
        self.assertEqual(sum(r['bytes'] for r in copies),500*45*80*13)

if __name__=='__main__':unittest.main(verbosity=2)
