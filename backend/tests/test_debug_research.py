"""Debug research endpoints."""
from __future__ import annotations

import httpx
import pytest
from asgi_lifespan import LifespanManager

from main import app


@pytest.mark.asyncio
async def test_debug_research_endpoint_returns_bundle_shape_without_key():
    original_key = app.state.settings.exa_api_key if hasattr(app.state, "settings") else None
    transport = httpx.ASGITransport(app=app)
    async with LifespanManager(app), httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        app.state.settings.exa_api_key = None
        response = await client.get("/debug/research", params={"prompt": "a medieval cottage"})

    app.state.settings.exa_api_key = original_key
    assert response.status_code == 200
    payload = response.json()
    assert payload["prompt"] == "a medieval cottage"
    assert payload["visual_descriptions"] == []
    assert payload["images"] == []
    assert payload["cached"] is False


@pytest.mark.asyncio
async def test_debug_research_ui_loads():
    transport = httpx.ASGITransport(app=app)
    async with LifespanManager(app), httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.get("/debug/research-ui")

    assert response.status_code == 200
    assert "Exa Research Debug" in response.text
    assert "/debug/research?prompt=" in response.text
