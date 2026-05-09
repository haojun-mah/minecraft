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

from api.schemas import BuildResult
from pipeline.encode import encode_rle_zyx


SAMPLE_PALETTE: list[str] = [
    "minecraft:air",
    "minecraft:cobblestone",
    "minecraft:oak_planks",
    "minecraft:hay_block",
]
SAMPLE_SIZE: tuple[int, int, int] = (5, 5, 5)


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


def build_sample_response(*, job_id: str, prompt: str) -> BuildResult:
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
        hero_image_url=None,
        preview_image_url=None,
    )
