"""Hard-coded sample response used by Phase 1 and `scripts/freeze_sample.py`.

Builds a tiny 5x5x5 cottage:
    y=0       cobblestone floor (5x5)
    y=1, y=2  oak_planks walls (border ring), air interior
    y=3       hay_block roof (5x5)
    y=4       all air

This is a deterministic sample so the frontend mod can render and verify
the decode pipeline before the real generative pipeline is ready.
"""
from __future__ import annotations

import json
from pathlib import Path

from api.schemas import BuildResult
from pipeline.encode import encode_rle_zyx


SAMPLE_PALETTE: list[str] = [
    "minecraft:air",
    "minecraft:cobblestone",
    "minecraft:oak_planks",
    "minecraft:hay_block",
]
SAMPLE_SIZE: tuple[int, int, int] = (5, 5, 5)
SAMPLE_RESPONSE_PATH = Path(__file__).resolve().parent.parent / "examples" / "sample_response.json"
FlatBlock = dict[str, int | str]


def _build_sample_grid() -> list[list[list[int]]]:
    sx, sy, sz = SAMPLE_SIZE
    grid = [[[0 for _ in range(sz)] for _ in range(sy)] for _ in range(sx)]
    for x in range(sx):
        for z in range(sz):
            grid[x][0][z] = 1
            grid[x][3][z] = 3
    for y in (1, 2):
        for x in range(sx):
            for z in range(sz):
                if x == 0 or x == sx - 1 or z == 0 or z == sz - 1:
                    grid[x][y][z] = 2
    return grid


def build_sample_flat_blocks() -> list[FlatBlock]:
    grid = _build_sample_grid()
    entries: list[FlatBlock] = []
    sx, sy, sz = SAMPLE_SIZE
    for z in range(sz):
        for y in range(sy):
            for x in range(sx):
                block = SAMPLE_PALETTE[grid[x][y][z]]
                if block != "minecraft:air":
                    entries.append({"x": x, "y": y, "z": z, "block": block})
    return entries


def build_sample_response(
    *,
    job_id: str,
    prompt: str,
    input_image_url: str | None = None,
    hero_image_url: str | None = None,
    preview_image_url: str | None = None,
) -> BuildResult:
    grid = _build_sample_grid()
    encoded = encode_rle_zyx(grid, SAMPLE_SIZE)
    return BuildResult(
        job_id=job_id,
        prompt=prompt,
        size=SAMPLE_SIZE,
        origin=(0, 0, 0),
        palette=SAMPLE_PALETTE,
        blocks=encoded,
        encoding="rle-z-y-x",
        hero_image_url=hero_image_url,
        preview_image_url=preview_image_url,
        input_image_url=input_image_url,
    )


def load_forced_sample_response(
    *,
    job_id: str,
    prompt: str,
    input_image_url: str | None = None,
    hero_image_url: str | None = None,
    preview_image_url: str | None = None,
) -> BuildResult:
    """Load the canonical frontend sample response and reuse its block payload.

    The API keeps the live job metadata but forces the final block payload from
    examples/sample_response.json so frontend placement can be tested against a
    stable known structure.
    """
    blocks = load_forced_sample_blocks()
    palette = ["minecraft:air"]
    palette_index = {"minecraft:air": 0}
    max_x = max((int(block["x"]) for block in blocks), default=0)
    max_y = max((int(block["y"]) for block in blocks), default=0)
    max_z = max((int(block["z"]) for block in blocks), default=0)
    size = (
        max(SAMPLE_SIZE[0], max_x + 1),
        max(SAMPLE_SIZE[1], max_y + 1),
        max(SAMPLE_SIZE[2], max_z + 1),
    )
    grid = [[[0 for _ in range(size[2])] for _ in range(size[1])] for _ in range(size[0])]

    for block in blocks:
        block_id = str(block["block"])
        if block_id not in palette_index:
            palette_index[block_id] = len(palette)
            palette.append(block_id)
        grid[int(block["x"])][int(block["y"])][int(block["z"])] = palette_index[block_id]

    return BuildResult(
        job_id=job_id,
        prompt=prompt,
        size=size,
        origin=(0, 0, 0),
        palette=palette,
        blocks=encode_rle_zyx(grid, size),
        encoding="rle-z-y-x",
        hero_image_url=hero_image_url,
        preview_image_url=preview_image_url,
        input_image_url=input_image_url,
    )


def load_forced_sample_blocks() -> list[FlatBlock]:
    data = json.loads(SAMPLE_RESPONSE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("examples/sample_response.json must contain a flat block list")
    return data
