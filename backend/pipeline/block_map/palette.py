"""Vanilla Minecraft block palette loading and Lab conversion."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from skimage.color import rgb2lab


@dataclass(frozen=True)
class BlockPalette:
    block_ids: list[str]
    rgb: np.ndarray
    lab: np.ndarray

    def __post_init__(self) -> None:
        if len(self.block_ids) != len(self.rgb) or len(self.block_ids) != len(self.lab):
            raise ValueError("Palette block_ids, rgb, and lab arrays must have matching lengths")


def load_block_palette(path: Path) -> BlockPalette:
    """Load a curated palette JSON file and convert colors to CIE Lab."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    block_ids: list[str] = []
    rgb_values: list[list[int]] = []
    seen: set[str] = set()
    for item in raw:
        block_id = str(item["block_id"])
        if block_id == "minecraft:air":
            continue
        if block_id in seen:
            raise ValueError(f"Duplicate block in palette: {block_id}")
        seen.add(block_id)
        rgb = [int(channel) for channel in item["rgb"]]
        if len(rgb) != 3 or any(channel < 0 or channel > 255 for channel in rgb):
            raise ValueError(f"Invalid RGB for {block_id}: {rgb}")
        block_ids.append(block_id)
        rgb_values.append(rgb)

    if not block_ids:
        raise ValueError(f"Palette is empty: {path}")

    rgb_array = np.asarray(rgb_values, dtype=np.uint8)
    lab_array = rgb2lab((rgb_array.astype(np.float32) / 255.0).reshape(-1, 1, 3)).reshape(-1, 3)
    return BlockPalette(block_ids=block_ids, rgb=rgb_array, lab=lab_array.astype(np.float32))
