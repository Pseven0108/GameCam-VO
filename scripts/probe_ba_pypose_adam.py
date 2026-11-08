"""Isolated optimizer diagnostic; never patches a model or loads engine GT."""
from pathlib import Path
import inspect
import json
import torch
import pypose as pp
import torch.optim.adam as adam_module


class ObservedParameter(pp.Parameter):
    add_calls = 0

    def add_(self, other, alpha=1):
        type(self).add_calls += 1
        return super().add_(other, alpha=alpha)


def main():
    records = []
    for device in ("cpu", "cuda"):
        for foreach in (None, False, True):
            torch.manual_seed(17)
            target = pp.randn_SE3(8, device=device)
            pose = ObservedParameter(pp.identity_SE3(8, device=device))
            ObservedParameter.add_calls = 0
            optimizer = torch.optim.Adam([pose], lr=.01, betas=(.9, .9), foreach=foreach)
            start = None
            for _ in range(30):
                optimizer.zero_grad()
                loss = (pose.Inv() * target).Log().tensor().square().mean()
                if start is None:
                    start = float(loss.detach())
                loss.backward()
                optimizer.step()
            matrix = pose.matrix().detach().cpu()
            q = pose.tensor().detach().cpu()[:, 3:]
            rotation = matrix[:, :3, :3]
            records.append({"device": device, "foreach": foreach, "steps": 30,
                            "manifold_add_calls": ObservedParameter.add_calls,
                            "initial_loss": start, "last_pre_update_loss": float(loss.detach()),
                            "max_quaternion_norm_error": float((q.norm(dim=-1)-1).abs().max()),
                            "max_RtR_error": float((rotation.transpose(-1, -2) @ rotation-torch.eye(3)).abs().max())})
    result = {"status": "ISOLATED_DIAGNOSTIC_COMPLETED", "torch": torch.__version__, "pypose": pp.__version__,
              "model_or_optimizer_patch_applied": False, "inference_results_modified": False,
              "single_tensor_adam_uses_addcdiv": "param.addcdiv_" in inspect.getsource(adam_module._single_tensor_adam),
              "pypose_addcdiv_is_inherited_tensor_method": pp.Parameter.addcdiv_ is torch.Tensor.addcdiv_,
              "records": records,
              "interpretation": "Synthetic evidence only: Adam can bypass LieTensor.add_ and leave the unit-quaternion manifold. This is consistent with native dense pose drift but does not isolate its magnitude/cause in the full model. Preserve official optimizer unchanged.",
              "primary_sources": ["https://github.com/pypose/pypose/issues/377", "https://github.com/pytorch/pytorch/blob/v2.1.1/torch/optim/adam.py"]}
    root = Path(__file__).resolve().parents[1]
    (root / "reports/SOTA/ba_track_pypose_adam_diagnostic.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
