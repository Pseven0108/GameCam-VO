"""Small fixtures only; these objects are never a substitute for native C0."""
from collections import OrderedDict
import torch

class FixtureModel(torch.nn.Module):
    def __init__(self):
        super().__init__();self.layer=torch.nn.Linear(3,2)
        self.register_buffer('running_cache',torch.arange(9).reshape(3,3))
        self.register_buffer('scratch',torch.arange(3.),persistent=False)
        self.custom_cache={'position':torch.ones(1,3)}
    def forward(self,x):return self.layer(x)+self.scratch[:2]

class FixtureObject:
    def __init__(self):
        self.model=FixtureModel().eval();self.model.layer.train(True)
        self.cache=torch.arange(24,dtype=torch.float32).reshape(4,6)
        self.transpose=self.cache.T;self.view=self.cache[1:,1:5];self.same_view=self.view
        self.update_op=self.model.forward;self.generator=torch.Generator().manual_seed(43)
        self.corr_pyramid=[self.cache,self.cache[::2]]
        self.loop_cursor={'next_input_index':18,'prev_kf_idx':11,'prev_ba_idx':0}
        self.non_string_keys=OrderedDict([(3,'three'),((4,5),torch.tensor(9))])
        self.service=None;self.self_reference=self

class NoConstructorFixture:
    def __new__(cls):raise RuntimeError('A checkpoint restore must not call this constructor')

def fixture_bundle():
    a=FixtureObject()
    return {'tracker':a,'same_tracker':a,'input':torch.tensor([[1.,2.,3.]]),
            'flags':{'D':0,'W':1,'U':1},'cursor':{'next_input_index':18,'intrinsic':torch.tensor([386.,386.,319.5,179.5])}}
