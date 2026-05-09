"""Build API responses from final Minecraft block grids."""
from __future__ import annotations

from api.schemas import BuildResult
from pipeline.block_map.apply import CompactedBlockGrid, compact_block_grid
from pipeline.block_map.nearest import BlockGrid
from pipeline.encode import encode_rle_zyx


def build_result_from_block_grid(
    *,
    job_id: str,
    prompt: str,
    grid: BlockGrid,
    hero_image_url: str | None,
    input_image_url: str | None,
    preview_image_url: str | None = None,
) -> BuildResult:
    compacted = compact_block_grid(grid)
    return build_result_from_compacted_grid(
        job_id=job_id,
        prompt=prompt,
        compacted=compacted,
        hero_image_url=hero_image_url,
        input_image_url=input_image_url,
        preview_image_url=preview_image_url,
    )


def build_result_from_compacted_grid(
    *,
    job_id: str,
    prompt: str,
    compacted: CompactedBlockGrid,
    hero_image_url: str | None,
    input_image_url: str | None,
    preview_image_url: str | None = None,
) -> BuildResult:
    return BuildResult(
        job_id=job_id,
        prompt=prompt,
        size=compacted.size,
        origin=(0, 0, 0),
        palette=compacted.palette,
        blocks=encode_rle_zyx(compacted.indices, compacted.size),
        encoding="rle-z-y-x",
        hero_image_url=hero_image_url,
        preview_image_url=preview_image_url,
        input_image_url=input_image_url,
    )
