from __future__ import annotations

from gamecam_vo.common import PROJECT


def open_dataset(config: dict):
    name = config["adapter"]
    if name == "mvs_synth":
        from datasets.mvs_synth.adapter import MVSSynthDataset
        return MVSSynthDataset(config, PROJECT)
    if name == "omniworld_game":
        from datasets.omniworld_game.adapter import OmniWorldGameDataset
        return OmniWorldGameDataset(config, PROJECT)
    if name == "wildworld":
        from datasets.wildworld.adapter import WildWorldDataset
        return WildWorldDataset(config, PROJECT)
    raise ValueError(f"Unsupported dataset adapter: {name}")
