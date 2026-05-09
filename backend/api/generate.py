"""POST /generate — synchronous wrapper for the Minecraft frontend mod.

Accepts {"prompt": "..."} and returns the forced flat block sample the mod
can place directly.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from storage.sample import FlatBlock, load_forced_sample_blocks

logger = logging.getLogger(__name__)
router = APIRouter(tags=["generate"])


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=500)


@router.post("/generate")
async def generate(body: GenerateRequest) -> list[FlatBlock]:
    blocks = load_forced_sample_blocks()
    logger.info("[generate] forced sample for prompt %r — %d blocks", body.prompt, len(blocks))
    return blocks
