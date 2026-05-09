"""Tests for OpenAI semantic block refinement."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from config import Settings
from pipeline.block_map.semantic import semantic_refine_blocks


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeResponse(self.content)


class _FakeChat:
    def __init__(self, content: str) -> None:
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = _FakeChat(content)


@pytest.mark.asyncio
async def test_semantic_refine_applies_valid_mappings_and_ignores_invalid(tmp_path: Path):
    client = _FakeClient(
        json.dumps(
            {
                "remap": {
                    "minecraft:brown_concrete": "minecraft:oak_planks",
                    "minecraft:unknown": "minecraft:diamond_block",
                    "minecraft:yellow_concrete": "minecraft:not_allowed",
                },
                "reasoning_summary": "Wood-like colors should become planks.",
            }
        )
    )
    settings = Settings(openai_api_key="test", openai_block_refine_enabled=True)

    result = await semantic_refine_blocks(
        prompt="a cottage",
        style_hint=None,
        histogram={"minecraft:brown_concrete": 5, "minecraft:yellow_concrete": 2},
        allowed_blocks=["minecraft:oak_planks", "minecraft:hay_block"],
        output_path=tmp_path / "block_refine.json",
        settings=settings,
        client=client,
    )

    assert result.remap == {"minecraft:brown_concrete": "minecraft:oak_planks"}
    assert "Wood-like" in result.reasoning_summary
    assert (tmp_path / "block_refine.json").exists()


@pytest.mark.asyncio
async def test_semantic_refine_failure_falls_back_to_identity(tmp_path: Path):
    result = await semantic_refine_blocks(
        prompt="a cottage",
        style_hint=None,
        histogram={"minecraft:brown_concrete": 5},
        allowed_blocks=["minecraft:oak_planks"],
        output_path=tmp_path / "block_refine.json",
        settings=Settings(openai_api_key=None, openai_block_refine_enabled=True),
        client=None,
    )

    assert result.remap == {}
    assert result.error is not None
    saved = json.loads((tmp_path / "block_refine.json").read_text())
    assert saved["error"] is not None
