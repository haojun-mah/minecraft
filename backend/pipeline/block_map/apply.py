"""Apply semantic remaps and compact block grids for API responses."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from pipeline.block_map.nearest import BlockGrid


@dataclass(frozen=True)
class CompactedBlockGrid:
    size: tuple[int, int, int]
    palette: list[str]
    indices: np.ndarray

    def __post_init__(self) -> None:
        if self.indices.shape != self.size:
            raise ValueError(f"indices shape {self.indices.shape} does not match size {self.size}")
        if not self.palette or self.palette[0] != "minecraft:air":
            raise ValueError("Compacted palette must start with minecraft:air")


def apply_semantic_remap(grid: BlockGrid, remap: dict[str, str]) -> BlockGrid:
    if not remap:
        return grid
    blocks = grid.blocks.copy()
    for source, target in remap.items():
        blocks[blocks == source] = target
    unique, counts = np.unique(blocks[blocks != "minecraft:air"], return_counts=True)
    histogram = {str(block_id): int(count) for block_id, count in zip(unique, counts, strict=True)}
    return BlockGrid(size=grid.size, blocks=blocks, histogram=histogram)


def compact_block_grid(grid: BlockGrid) -> CompactedBlockGrid:
    palette = ["minecraft:air"]
    seen = {"minecraft:air"}
    for value in grid.blocks.ravel(order="C"):
        block_id = str(value)
        if block_id not in seen:
            seen.add(block_id)
            palette.append(block_id)
    if len(palette) > 256:
        raise ValueError(f"Response palette has {len(palette)} entries; max is 256")

    index_by_block = {block_id: index for index, block_id in enumerate(palette)}
    indices = np.zeros(grid.size, dtype=np.uint8)
    for block_id, index in index_by_block.items():
        if index == 0:
            continue
        indices[grid.blocks == block_id] = index
    return CompactedBlockGrid(size=grid.size, palette=palette, indices=indices)


def save_compacted_grid(grid: CompactedBlockGrid, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        size=np.asarray(grid.size),
        palette=np.asarray(grid.palette, dtype=object),
        indices=grid.indices,
    )
