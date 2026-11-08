"""Read official metadata and local resources; never download model weights."""
from __future__ import annotations
import _bootstrap
import importlib.util
import json
from pathlib import Path
from gamecam_vo.common import PROJECT, run_metadata, write_json


def main():
    source = PROJECT / "docs/sources/monst3r"
    revision = json.loads((source / "revision.json").read_text())
    metadata = json.loads((source / "model_metadata.json").read_text())
    tree = json.loads((source / "model_tree.json").read_text())
    weight = next(row for row in tree if row["path"] == "model.safetensors")
    result = {**run_metadata(), "experiment_id": "E3_OMNI", "POSE_PROVENANCE": "ESTIMATED_REFERENCE",
              "status": "NOT_RUN_LARGE_WEIGHTS_APPROVAL_REQUIRED", "inference_attempted": False,
              "official_code": revision, "official_model_id": metadata["id"], "official_model_revision": metadata["sha"],
              "main_weight_path": weight["path"], "main_weight_bytes": weight["size"], "main_weight_sha256": weight["lfs"]["oid"],
              "main_weight_downloaded": False, "model_asset_bytes_downloaded_this_project": 0,
              "license": "CC-BY-NC-SA-4.0", "torch_installed_in_project_environment": importlib.util.find_spec("torch") is not None,
              "observed_gpu": "NVIDIA GeForce RTX 5060, 8151 MiB", "host_ram_gib": 15.89,
              "official_memory_reference": "README reports about 33GB for 65 frames at 16:9, about 23GB with not_batchify; these are source-reported, not this machine's measurements",
              "official_download_script_other_assets": ["RAFT models.zip", "SEA-RAFT checkpoint", "sam2.1_hiera_large.pt"],
              "other_assets_exact_combined_bytes": None,
              "approval_basis": "Original user task prohibits unapproved large model/download/resource consumption; mirror approval only covered MVS sequence 0000",
              "proposed_next_stage": {"input": "First 4 original Omni RGB frames, recorded explicit frame IDs, smoke test only",
                   "main_weight": {"revision": metadata["sha"], "bytes": weight["size"], "sha256": weight["lfs"]["oid"]},
                   "asset_policy": "Do not run upstream all-assets download script blindly; inspect required flow/SAM assets before each bounded download",
                   "runtime_policy": "Separate conda gamecam-monst3r environment, verify CUDA/PyTorch compatibility before installing; main gamecam-vo remains usable",
                   "candidate_options": "batch_size=1, image_size=512, not_batchify; validate repository-supported small-window or realtime mode separately",
                   "stopping_conditions": "No full-sequence result claimed from smoke test; report OOM without fabricated trajectories; stop if approved network/disk budget would be exceeded",
                   "total_installation_budget": "Not yet approved; dependencies and auxiliary checkpoints are additional to 2.28GB main weight"}}
    write_json(PROJECT / "reports/monst3r_preflight.json", result)
    text = f'''# E3_OMNI / MonST3R 前置检查

POSE_PROVENANCE = ESTIMATED_REFERENCE

状态：**{result['status']}**。尚未安装/运行模型，没有推理耗时、显存实测或轨迹指标；不能写成模型推理失败。

官方代码固定 `{revision['revision']}`；权重仓库 `{metadata['id']}`，修订 `{metadata['sha']}`。`model.safetensors` 为 **{weight['size']:,} bytes**，LFS SHA256 `{weight['lfs']['oid']}`，本项目下载权重字节数 0。代码与权重许可为 CC-BY-NC-SA 4.0。

目前 RTX 5060 显存 8151 MiB，主机 RAM 15.89 GiB，gamecam-vo 无 PyTorch。官方 README 所述 65 帧 16:9 优化约需 33GB 显存，`--not_batchify` 约 23GB；这是作者报告，不能当成本机测试。8GB 上必须先试少量帧，不能承诺完整 132 帧能运行。

官方 `data/download_ckpt.sh` 还会下载 RAFT、SEA-RAFT、SAM2。没有执行此脚本；附属资产总大小尚未确定，不虚构总预算，也不让模型库隐式自动下载。CUDA/PyTorch 与本 GPU 的兼容性未验证，不照搬 README 中旧 CUDA 安装命令。

下一步可审查的方案：单独 Conda 环境 `gamecam-monst3r`；固定上述模型修订及 SHA256，只取当前场景前 4 个原始 RGB 帧做 smoke test，候选 `batch_size=1`、`--not_batchify`。先验证官方小窗口或 realtime 入口的实际依赖，再逐项列出额外下载量。小样本结果不能冒充全序列基线。主权重之外的依赖与辅助资产需要另列预算。

暂停大型下载的依据是原任务“涉及大规模数据下载……或高额资源消耗时，必须先停止并说明”。本次“允许”对应 MVS 镜像 0000 的明确许可，未外推成所有权重下载许可。此限制没有阻止其他已授权实验。

官方来源：[README](https://github.com/Junyi42/monst3r/blob/{revision['revision']}/README.md)、[下载脚本](https://github.com/Junyi42/monst3r/blob/{revision['revision']}/data/download_ckpt.sh)、[推理入口](https://github.com/Junyi42/monst3r/blob/{revision['revision']}/demo.py)、[模型文件](https://huggingface.co/{metadata['id']}/tree/{metadata['sha']})。元数据快照位于 docs/sources/monst3r/。
'''
    (PROJECT / "reports/monst3r_preflight.md").write_text(text, encoding="utf-8")
    print(json.dumps({"status": result["status"], "main_weight_bytes": weight["size"], "inference_attempted": False}))


if __name__ == "__main__":
    main()
