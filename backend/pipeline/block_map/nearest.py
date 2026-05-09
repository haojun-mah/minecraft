"""Deterministic RGB -> Minecraft block mapping."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from skimage.color import rgb2lab

from pipeline.block_map.palette import BlockPalette
from pipeline.voxelize import VoxelizedMesh


@dataclass(frozen=True)
class BlockGrid:
    size: tuple[int, int, int]
    blocks: np.ndarray
    histogram: dict[str, int]

    def __post_init__(self) -> None:
        if self.blocks.shape != self.size:
            raise ValueError(f"blocks shape {self.blocks.shape} does not match size {self.size}")


def map_rgb_to_blocks(voxels: VoxelizedMesh, palette: BlockPalette) -> BlockGrid:
    """Map every filled voxel to the nearest palette block in CIE Lab space."""
    blocks = np.full(voxels.size, "minecraft:air", dtype=object)
    if not voxels.filled.any():
        return BlockGrid(size=voxels.size, blocks=blocks, histogram={})

    rgb = voxels.rgb[voxels.filled].astype(np.float32) / 255.0
    lab = rgb2lab(rgb.reshape(-1, 1, 3)).reshape(-1, 3).astype(np.float32)
    distances = np.sum((lab[:, None, :] - palette.lab[None, :, :]) ** 2, axis=2)
    nearest = np.argmin(distances, axis=1)
    mapped = np.asarray([palette.block_ids[index] for index in nearest], dtype=object)
    blocks[voxels.filled] = mapped
    histogram = dict(Counter(str(block_id) for block_id in mapped))
    return BlockGrid(size=voxels.size, blocks=blocks, histogram=histogram)


def save_block_grid(grid: BlockGrid, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    block_ids = np.asarray(sorted(grid.histogram), dtype=object)
    np.savez_compressed(
        path,
        size=np.asarray(grid.size),
        blocks=grid.blocks.astype(str),
        block_ids=block_ids,
        counts=np.asarray([grid.histogram[str(block_id)] for block_id in block_ids]),
    )
