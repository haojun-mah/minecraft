"""Offline tests for the Exa research stage."""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import httpx
import pytest
import respx
from PIL import Image

from config import Settings
from pipeline.exa_client import EXA_SEARCH_URL
from pipeline.research import load_research_bundle, research


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "exa_response.json"
VALID_IMAGE_URLS = [
    "https://images.example.com/cottage-main.jpg",
    "https://images.example.com/cottage-side.png",
    "https://images.example.com/roof.webp",
    "https://images.example.com/detail.jpeg",
    "https://images.example.com/minecraft-cottage.jpg",
    "https://images.example.com/minecraft-cottage-alt.png",
]


def _settings(tmp_path: Path, *, api_key: str | None = "test-exa-key") -> Settings:
    return Settings(
        exa_api_key=api_key,
        artifacts_dir=tmp_path,
        exa_num_results=8,
        exa_image_links_per_result=3,
        exa_cache_ttl_days=7,
    )


def _fixture_response() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _png_bytes(size: tuple[int, int] = (64, 64), color: str = "red") -> bytes:
    image = Image.new("RGB", size, color=color)
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _mock_exa_and_images(response: dict) -> None:
    respx.post(EXA_SEARCH_URL).mock(return_value=httpx.Response(200, json=response))
    for url in VALID_IMAGE_URLS:
        respx.get(url).mock(
            return_value=httpx.Response(
                200,
                content=_png_bytes(),
                headers={"content-type": "image/png"},
            )
        )


@pytest.mark.asyncio
@respx.mock
async def test_happy_path(tmp_path: Path):
    _mock_exa_and_images(_fixture_response())

    bundle = await research(
        "a medieval cottage",
        job_id="j_test",
        artifacts_dir=tmp_path,
        settings=_settings(tmp_path),
    )

    assert bundle.cached is False
    assert bundle.manifest_path == tmp_path / "j_test" / "research_bundle.json"
    assert bundle.manifest_path.exists()
    assert len(bundle.visual_descriptions) == 5
    assert len(bundle.images) == 4
    assert all("http" not in item.description for item in bundle.visual_descriptions)
    for image in bundle.images:
        assert image.path.exists()
        assert image.width == 64
        assert image.height == 64
        assert image.static_url.startswith("/static/j_test/refs/ref_")
        assert image.description.startswith("Architectural visual detail")

    loaded = load_research_bundle(artifacts_dir=tmp_path, job_id="j_test")
    assert loaded.manifest_path == bundle.manifest_path
    assert loaded.visual_descriptions == bundle.visual_descriptions
    assert [image.path for image in loaded.images] == [image.path for image in bundle.images]


@pytest.mark.asyncio
@respx.mock
async def test_exa_request_is_architecture_focused(tmp_path: Path):
    route = respx.post(EXA_SEARCH_URL).mock(return_value=httpx.Response(200, json={"results": []}))

    await research(
        "a medieval cottage",
        job_id="j_architecture_query",
        artifacts_dir=tmp_path,
        settings=_settings(tmp_path),
    )

    request_body = json.loads(route.calls.last.request.content)
    assert request_body["query"].startswith("a medieval cottage")
    assert "architectural visual reference" in request_body["query"]
    assert "roof walls windows doors" in request_body["query"]
    assert "systemPrompt" in request_body
    assert "architectural and pictorial details" in request_body["systemPrompt"]
    highlight_query = request_body["contents"]["highlights"]["query"]
    assert "roof" in highlight_query
    assert "materials" in highlight_query


@pytest.mark.asyncio
@respx.mock
async def test_filters_unsupported_image_extensions(tmp_path: Path):
    _mock_exa_and_images(_fixture_response())

    bundle = await research(
        "a medieval cottage",
        job_id="j_filter",
        artifacts_dir=tmp_path,
        settings=_settings(tmp_path),
    )

    filenames = {image.path.name for image in bundle.images}
    assert filenames == {"ref_0.jpg", "ref_1.jpg", "ref_2.jpg", "ref_3.jpg"}


@pytest.mark.asyncio
@respx.mock
async def test_zero_results(tmp_path: Path):
    respx.post(EXA_SEARCH_URL).mock(return_value=httpx.Response(200, json={"results": []}))

    bundle = await research(
        "nothing relevant",
        job_id="j_zero",
        artifacts_dir=tmp_path,
        settings=_settings(tmp_path),
    )

    assert bundle.cached is False
    assert bundle.visual_descriptions == []
    assert bundle.images == []


@pytest.mark.asyncio
async def test_missing_api_key(tmp_path: Path):
    with respx.mock(assert_all_called=False) as router:
        bundle = await research(
            "a medieval cottage",
            job_id="j_no_key",
            artifacts_dir=tmp_path,
            settings=_settings(tmp_path, api_key=None),
        )

    assert len(router.calls) == 0
    assert bundle.cached is False
    assert bundle.visual_descriptions == []
    assert bundle.images == []


@pytest.mark.asyncio
@respx.mock
async def test_network_failure(tmp_path: Path):
    respx.post(EXA_SEARCH_URL).mock(side_effect=httpx.ConnectError("network down"))

    bundle = await research(
        "a medieval cottage",
        job_id="j_network",
        artifacts_dir=tmp_path,
        settings=_settings(tmp_path),
    )

    assert bundle.cached is False
    assert bundle.visual_descriptions == []
    assert bundle.images == []


@pytest.mark.asyncio
async def test_cache_hit(tmp_path: Path):
    with respx.mock(assert_all_called=False) as router:
        exa_route = router.post(EXA_SEARCH_URL).mock(
            return_value=httpx.Response(200, json=_fixture_response())
        )
        image_routes = [
            router.get(url).mock(
                return_value=httpx.Response(
                    200,
                    content=_png_bytes(),
                    headers={"content-type": "image/png"},
                )
            )
            for url in VALID_IMAGE_URLS
        ]
        settings = _settings(tmp_path)

        first = await research(
            "a medieval cottage",
            job_id="j_cache_1",
            artifacts_dir=tmp_path,
            settings=settings,
        )
        second = await research(
            "A Medieval Cottage",
            job_id="j_cache_2",
            artifacts_dir=tmp_path,
            settings=settings,
        )

        assert first.cached is False
        assert second.cached is True
        assert second.manifest_path == tmp_path / "j_cache_2" / "research_bundle.json"
        assert second.manifest_path.exists()
        assert exa_route.call_count == 1
        assert sum(route.call_count for route in image_routes) == 6
        assert len(second.images) == 4
        for image in second.images:
            assert image.path.exists()
            assert "/static/j_cache_2/refs/" in image.static_url


@pytest.mark.asyncio
@respx.mock
async def test_image_too_large(tmp_path: Path):
    response = {
        "results": [
            {
                "title": "Huge image",
                "url": "https://example.com/huge",
                "highlights": ["A reference with one huge image and one normal image."],
                "image": "https://images.example.com/huge.jpg",
                "extras": {"imageLinks": ["https://images.example.com/normal.jpg"]},
            }
        ]
    }
    respx.post(EXA_SEARCH_URL).mock(return_value=httpx.Response(200, json=response))
    respx.get("https://images.example.com/huge.jpg").mock(
        return_value=httpx.Response(
            200,
            content=b"x" * (6 * 1024 * 1024),
            headers={"content-type": "image/jpeg"},
        )
    )
    respx.get("https://images.example.com/normal.jpg").mock(
        return_value=httpx.Response(
            200,
            content=_png_bytes(),
            headers={"content-type": "image/png"},
        )
    )

    bundle = await research(
        "a medieval cottage",
        job_id="j_large",
        artifacts_dir=tmp_path,
        settings=_settings(tmp_path),
    )

    assert len(bundle.images) == 1
    assert bundle.images[0].path.name == "ref_0.jpg"
