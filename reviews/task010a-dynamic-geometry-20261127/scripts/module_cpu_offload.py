"""Read-only FP32 parameter offload for independent inference, no source rewrite."""
import torch


class FrozenModuleOffload:
    """Stage direct parameters/buffers around each module call.

    Original CPU checkpoint tensors remain referenced unchanged. Post hooks
    restore those exact objects, rather than copying GPU results back. Use only
    frozen inference; disable autocast's weight cache to bound GPU residency.
    """
    def __init__(self,model,device='cuda'):
        self.device=device;self.handles=[];self.originals=[];self.calls=0
        for module in model.modules():
            parameters=dict(module._parameters);buffers=dict(module._buffers)
            if not any(t is not None for t in [*parameters.values(),*buffers.values()]):continue
            if any(t is not None and t.device.type!='cpu' for t in [*parameters.values(),*buffers.values()]):
                raise ValueError('Offload requires original CPU-only model storage')
            self.originals.append((module,parameters,buffers))
            def pre(mod,args,parameters=parameters,buffers=buffers):
                for name,value in parameters.items():
                    if value is not None:mod._parameters[name]=torch.nn.Parameter(value.to(self.device),requires_grad=False)
                for name,value in buffers.items():
                    if value is not None:mod._buffers[name]=value.to(self.device)
                self.calls+=1
            def post(mod,args,output,parameters=parameters,buffers=buffers):
                mod._parameters.update(parameters);mod._buffers.update(buffers)
            self.handles.append(module.register_forward_pre_hook(pre))
            self.handles.append(module.register_forward_hook(post,always_call=True))

    def restored(self):
        return all(all(module._parameters[k] is v for k,v in p.items()) and
                   all(module._buffers[k] is v for k,v in b.items()) for module,p,b in self.originals)

    def close(self):
        for h in self.handles:h.remove()
        self.handles.clear()
        for module,p,b in self.originals:module._parameters.update(p);module._buffers.update(b)
