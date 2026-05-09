"""API request/response schemas — the public contract with the frontend mod."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


JobStatus = Literal["queued", "running", "done", "error"]
PipelineStage = Literal[
    "queued",
    "research",
    "planning",
    "image_gen",
    "image_to_3d",
    "voxelizing",
    "block_mapping",
    "encoding",
    "done",
]


class BuildRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=500)
    max_size: tuple[int, int, int] = Field(
        (48, 48, 48),
        description="Max bounding box (X, Y, Z). Final size may be smaller.",
    )
    style_hint: str | None = Field(
        None,
        description="Optional style hint, e.g. 'blocky low-poly', 'realistic'.",
    )
    seed: int | None = Field(None, description="Optional seed for reproducibility.")
    input_image_url: str | None = Field(
        None,
        description="Optional static URL for an uploaded source image.",
    )


class BuildEnqueued(BaseModel):
    job_id: str
    status: JobStatus = "queued"


class BuildStatus(BaseModel):
    job_id: str
    status: JobStatus
    stage: PipelineStage
    progress: float = Field(0.0, ge=0.0, le=1.0)
    error: str | None = None


class BuildResult(BaseModel):
    """Final response when status == 'done'.

    The frontend decodes `blocks` (RLE -> bytes) using the size and palette
    to reconstruct the voxel grid. See README for the decode algorithm.
    """

    job_id: str
    status: Literal["done"] = "done"
    prompt: str
    size: tuple[int, int, int] = Field(..., description="(X, Y, Z) dimensions in blocks.")
    origin: tuple[int, int, int] = Field(
        (0, 0, 0),
        description="Origin offset relative to the player-chosen build location.",
    )
    palette: list[str] = Field(
        ...,
        description="Palette of Minecraft block IDs. Index 0 is always 'minecraft:air'.",
    )
    blocks: str = Field(
        ...,
        description="Base64-encoded RLE byte stream over the size grid.",
    )
    encoding: Literal["rle-z-y-x"] = Field(
        "rle-z-y-x",
        description="Iteration order: outer z, then y, then x. RLE = pairs of (count, palette_index) bytes.",
    )
    hero_image_url: str | None = None
    preview_image_url: str | None = None
    input_image_url: str | None = None
