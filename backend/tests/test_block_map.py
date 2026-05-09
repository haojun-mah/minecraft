"""Tests for deterministic block mapping and response compaction."""
from __future__ import annotations

import numpy as np

from pipeline.block_map.apply import apply_semantic_remap, compact_block_grid
from pipeline.block_map.nearest import BlockGrid, map_rgb_to_blocks
from pipeline.block_map.palette import BlockPalette, load_block_palette
from pipeline.encode import decode_rle_zyx
from pipeline.structure_result import build_result_from_block_grid
from pipeline.voxelize import VoxelizedMesh


def _test_palette() -> BlockPalette:
    return load_block_palette(__import__("pathlib").Path("data/block_palette.json"))


def test_nearest_mapping_keeps_air_and_maps_filled_voxels():
    filled = np.zeros((2, 1, 1), dtype=bool)
    filled[0, 0, 0] = True
    rgb = np.zeros((2, 1, 1, 3), dtype=np.uint8)
    rgb[0, 0, 0] = [165, 130, 80]
    voxels = VoxelizedMesh(size=(2, 1, 1), filled=filled, rgb=rgb)

    grid = map_rgb_to_blocks(voxels, _test_palette())

    assert grid.blocks[1, 0, 0] == "minecraft:air"
    assert grid.blocks[0, 0, 0] != "minecraft:air"
    assert sum(grid.histogram.values()) == 1


def test_semantic_remap_and_compaction_preserve_air_index_zero():
    blocks = np.asarray([[["minecraft:brown_concrete"]], [["minecraft:air"]]], dtype=object)
    grid = BlockGrid(size=(2, 1, 1), blocks=blocks, histogram={"minecraft:brown_concrete": 1})

    remapped = apply_semantic_remap(grid, {"minecraft:brown_concrete": "minecraft:oak_planks"})
    compacted = compact_block_grid(remapped)

    assert remapped.blocks[0, 0, 0] == "minecraft:oak_planks"
    assert compacted.palette[0] == "minecraft:air"
    assert compacted.indices[1, 0, 0] == 0
    assert compacted.palette[int(compacted.indices[0, 0, 0])] == "minecraft:oak_planks"


def test_build_result_from_block_grid_round_trips():
    blocks = np.asarray([[["minecraft:oak_planks"]], [["minecraft:air"]]], dtype=object)
    grid = BlockGrid(size=(2, 1, 1), blocks=blocks, histogram={"minecraft:oak_planks": 1})

    result = build_result_from_block_grid(
        job_id="j_test",
        prompt="test",
        grid=grid,
        hero_image_url=None,
        input_image_url=None,
    )

    assert result.palette == ["minecraft:air", "minecraft:oak_planks"]
    decoded = decode_rle_zyx(result.blocks, result.size)
    assert decoded[0][0][0] == 1
    assert decoded[1][0][0] == 0
