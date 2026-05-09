"""Unit tests for the OpenAI-backed hero-image generator."""
from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace

import pytest

from config import Settings
from pipeline.image_gen.openai_image import (
    OpenAIImageGenerator,
    build_hero_prompt,
    choose_hero_image_size,
)


class FakeImageClient:
    def __init__(self, payloads: list[str]) -> None:
        self._payloads = payloads
        self.calls: list[dict[str, object]] = []
        self.images = SimpleNamespace(generate=self._generate)

    def _generate(self, **kwargs):
        self.calls.append(kwargs)
        data = [
            SimpleNamespace(b64_json=payload, revised_prompt=f"revised-{index}")
            for index, payload in enumerate(self._payloads)
        ]
        return SimpleNamespace(data=data)


class FakeRankerClient:
    def __init__(self, output_text: str) -> None:
        self._output_text = output_text
        self.calls: list[dict[str, object]] = []
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=self._output_text)


@pytest.mark.asyncio
async def test_openai_image_generator_writes_candidates_and_picks_best(tmp_path: Path):
    candidate_0 = base64.b64encode(b"candidate-zero").decode("ascii")
    candidate_1 = base64.b64encode(b"candidate-one").decode("ascii")
    image_client = FakeImageClient([candidate_0, candidate_1])
    ranker_client = FakeRankerClient("1")

    generator = OpenAIImageGenerator(
        settings=Settings(openai_api_key="test-key"),
        client=image_client,
        ranker_client=ranker_client,
    )

    hero_path = await generator.generate(
        prompt=build_hero_prompt("a small medieval cottage", "blocky low-poly"),
        output_dir=tmp_path,
        size=choose_hero_image_size((48, 48, 48)),
        candidate_count=2,
    )

    assert hero_path.name == "hero.png"
    assert hero_path.read_bytes() == b"candidate-one"
    assert (tmp_path / "hero_candidate_0.png").read_bytes() == b"candidate-zero"
    assert (tmp_path / "hero_candidate_1.png").read_bytes() == b"candidate-one"
    assert image_client.calls[0]["model"] == "gpt-image-1"
    assert image_client.calls[0]["n"] == 2
    assert image_client.calls[0]["size"] == "1024x1024"
    assert image_client.calls[0]["quality"] == "medium"
    assert image_client.calls[0]["output_format"] == "png"
    assert ranker_client.calls[0]["model"] == "gpt-4.1-mini"
