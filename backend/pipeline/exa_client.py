"""Async Exa Search API client.

This module intentionally uses raw HTTP instead of the synchronous `exa-py`
SDK so it fits the async pipeline without threadpool wrappers.
"""
from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field


EXA_SEARCH_URL = "https://api.exa.ai/search"


class ExaError(RuntimeError):
    """Raised when Exa returns a non-success response or malformed payload."""


class ExaExtras(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    image_links: list[str] = Field(default_factory=list, alias="imageLinks")


class ExaResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    url: str
    text: str | None = None
    highlights: list[str] = Field(default_factory=list)
    image: str | None = None
    extras: ExaExtras | None = None


class ExaSearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    results: list[ExaResult] = Field(default_factory=list)


async def search_with_contents(
    query: str,
    *,
    api_key: str,
    num_results: int = 8,
    image_links_per_result: int = 3,
    timeout_s: float = 30.0,
    system_prompt: str | None = None,
    highlight_query: str | None = None,
) -> ExaSearchResponse:
    """Search Exa for visual context and image links relevant to `query`."""
    highlights: dict[str, Any] = {
        "numSentences": 2,
    }
    if highlight_query:
        highlights["query"] = highlight_query

    payload: dict[str, Any] = {
        "query": query,
        "type": "auto",
        "numResults": num_results,
        "contents": {
            "text": True,
            "highlights": highlights,
            "extras": {
                "imageLinks": image_links_per_result,
            },
        },
    }
    if system_prompt:
        payload["systemPrompt"] = system_prompt
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.post(EXA_SEARCH_URL, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise ExaError(f"Exa search request failed: {exc}") from exc

    if response.status_code >= 400:
        raise ExaError(
            f"Exa search returned HTTP {response.status_code}: {response.text[:500]}"
        )

    try:
        return ExaSearchResponse.model_validate(response.json())
    except ValueError as exc:
        raise ExaError("Exa search returned invalid JSON") from exc
