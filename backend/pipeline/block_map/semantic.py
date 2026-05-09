"""OpenAI-backed semantic block remapping."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import Settings, get_settings
from pipeline.research_types import ResearchBundle


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SemanticRemap:
    remap: dict[str, str]
    reasoning_summary: str = ""
    error: str | None = None


async def semantic_refine_blocks(
    *,
    prompt: str,
    style_hint: str | None,
    histogram: dict[str, int],
    allowed_blocks: list[str],
    research_bundle: ResearchBundle | None = None,
    output_path: Path | None = None,
    settings: Settings | None = None,
    client: Any | None = None,
) -> SemanticRemap:
    """Ask OpenAI for a global block remap, validating every returned block ID."""
    settings = settings or get_settings()
    if not settings.openai_block_refine_enabled:
        remap = SemanticRemap(remap={}, reasoning_summary="Semantic refinement disabled.")
        _write_refine_artifact(output_path, remap, histogram)
        return remap
    if not histogram:
        remap = SemanticRemap(remap={}, reasoning_summary="No filled blocks to refine.")
        _write_refine_artifact(output_path, remap, histogram)
        return remap

    try:
        raw = await asyncio.to_thread(
            _call_openai,
            prompt=prompt,
            style_hint=style_hint,
            histogram=histogram,
            allowed_blocks=allowed_blocks,
            research_bundle=research_bundle,
            settings=settings,
            client=client,
        )
        remap = _validate_response(raw, histogram, allowed_blocks)
    except Exception as exc:  # noqa: BLE001 - Stage A should still ship
        logger.exception("semantic block refinement failed")
        remap = SemanticRemap(remap={}, error=str(exc))

    _write_refine_artifact(output_path, remap, histogram)
    return remap


def _call_openai(
    *,
    prompt: str,
    style_hint: str | None,
    histogram: dict[str, int],
    allowed_blocks: list[str],
    research_bundle: ResearchBundle | None,
    settings: Settings,
    client: Any | None,
) -> dict[str, Any]:
    if client is None:
        if settings.openai_api_key is None:
            raise RuntimeError("OPENAI_API_KEY is required for semantic block refinement")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - deployment path
            raise RuntimeError("The openai package is required for semantic block refinement") from exc
        client = OpenAI(api_key=settings.openai_api_key)

    payload = _prompt_payload(
        prompt=prompt,
        style_hint=style_hint,
        histogram=histogram,
        allowed_blocks=allowed_blocks,
        research_bundle=research_bundle,
    )
    content = (
        "Remap Minecraft block IDs to create an architecturally diverse, realistic structure.\n\n"
        "RULES:\n"
        "1. Only remap block IDs that appear in stage_a_histogram.\n"
        "2. Every target must be from allowed_blocks. Never invent IDs.\n"
        "3. DIVERSITY IS REQUIRED: no single block may represent more than 30% of non-air voxels. "
        "If the histogram shows one block dominating, split it across multiple thematically appropriate blocks.\n"
        "4. Assign DIFFERENT blocks to different architectural zones:\n"
        "   - Foundation/base (bottom y-layer): stone, cobblestone, stone_bricks, deepslate_bricks\n"
        "   - Outer walls: planks, bricks, stone_bricks, concrete, terracotta\n"
        "   - Roof: logs, stairs, slabs, shingles-style blocks\n"
        "   - Interior floors: planks, stone, smooth_stone\n"
        "   - Trim/accent/detail: stairs, slabs, fences, chiseled variants\n"
        "5. Match the structure's style and period to the prompt and research_details.\n"
        "6. Map EACH source block to a DISTINCT target — do not funnel multiple sources to the same block.\n\n"
        "Return strict JSON with keys remap and reasoning_summary.\n\n"
        f"{json.dumps(payload, indent=2)}"
    )
    response = client.chat.completions.create(
        model=settings.openai_block_refine_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert Minecraft architect. Your job is to select rich, diverse, "
                    "period-accurate block palettes for voxel buildings. You always use many different "
                    "block types to make structures look realistic and visually interesting — never "
                    "defaulting to a single dominant material."
                ),
            },
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
    )
    text = response.choices[0].message.content
    if not text:
        raise RuntimeError("OpenAI returned an empty semantic remap response")
    return json.loads(text)


def _prompt_payload(
    *,
    prompt: str,
    style_hint: str | None,
    histogram: dict[str, int],
    allowed_blocks: list[str],
    research_bundle: ResearchBundle | None,
) -> dict[str, Any]:
    top_histogram = [
        {"block_id": block_id, "count": count}
        for block_id, count in sorted(histogram.items(), key=lambda item: item[1], reverse=True)[:25]
    ]
    research_details: list[str] = []
    if research_bundle is not None:
        research_details.extend(item.description for item in research_bundle.visual_descriptions[:5])
        research_details.extend(image.description for image in research_bundle.images[:4])
    return {
        "prompt": prompt,
        "style_hint": style_hint,
        "research_details": research_details,
        "stage_a_histogram": top_histogram,
        "allowed_blocks": allowed_blocks,
        "output_contract": {
            "remap": {"existing_block_id": "replacement_block_id"},
            "reasoning_summary": "short explanation",
        },
    }


def _validate_response(
    raw: dict[str, Any],
    histogram: dict[str, int],
    allowed_blocks: list[str],
) -> SemanticRemap:
    allowed_sources = set(histogram)
    allowed_targets = set(allowed_blocks)
    raw_remap = raw.get("remap", {})
    if not isinstance(raw_remap, dict):
        raw_remap = {}
    remap: dict[str, str] = {}
    for source, target in raw_remap.items():
        source_id = str(source)
        target_id = str(target)
        if source_id in allowed_sources and target_id in allowed_targets:
            remap[source_id] = target_id
    reasoning = raw.get("reasoning_summary", "")
    return SemanticRemap(remap=remap, reasoning_summary=str(reasoning))


def _write_refine_artifact(
    output_path: Path | None,
    result: SemanticRemap,
    histogram: dict[str, int],
) -> None:
    if output_path is None:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "remap": result.remap,
                "reasoning_summary": result.reasoning_summary,
                "error": result.error,
                "stage_a_histogram": histogram,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
