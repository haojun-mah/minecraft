"""Debug endpoints for manually validating backend pipeline stages."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from config import Settings
from pipeline.research import research
from pipeline.research_types import ResearchBundle


router = APIRouter(prefix="/debug", tags=["debug"])


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _artifacts_dir(request: Request) -> Path:
    return request.app.state.artifacts_dir


@router.get("/research", response_model=ResearchBundle)
async def debug_research(
    prompt: Annotated[str, Query(min_length=1, max_length=500)],
    settings: Annotated[Settings, Depends(_settings)],
    artifacts_dir: Annotated[Path, Depends(_artifacts_dir)],
) -> ResearchBundle:
    """Run the Exa research stage directly and return visual context as JSON."""
    digest = hashlib.sha256(prompt.strip().lower().encode("utf-8")).hexdigest()[:8]
    bundle = await research(
        prompt,
        job_id=f"debug_exa_{digest}",
        artifacts_dir=artifacts_dir,
        settings=settings,
    )
    print(
        "[debug/research]",
        {
            "prompt": bundle.prompt,
            "cached": bundle.cached,
            "visual_descriptions": len(bundle.visual_descriptions),
            "images": len(bundle.images),
            "descriptions": [item.description for item in bundle.visual_descriptions],
            "image_paths": [str(image.path) for image in bundle.images],
        },
        flush=True,
    )
    return bundle


@router.get("/research-ui", response_class=HTMLResponse)
async def debug_research_ui() -> str:
    """Small browser UI for manually testing Exa research."""
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Exa Research Debug</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 960px; margin: 40px auto; padding: 0 16px; }
    form { display: flex; gap: 8px; margin-bottom: 24px; }
    input { flex: 1; padding: 10px 12px; font-size: 16px; }
    button { padding: 10px 14px; font-size: 16px; cursor: pointer; }
    .muted { color: #666; }
    .error { color: #b00020; white-space: pre-wrap; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
    .card { border: 1px solid #ddd; border-radius: 8px; padding: 12px; }
    img { width: 100%; height: 160px; object-fit: cover; border-radius: 6px; background: #eee; }
    pre { background: #f6f8fa; padding: 12px; overflow: auto; border-radius: 8px; }
  </style>
</head>
<body>
  <h1>Exa Research Debug</h1>
  <p class="muted">Runs <code>GET /debug/research?prompt=...</code> and previews visual descriptions/images used to enrich GPT.</p>
  <form id="form">
    <input id="prompt" value="a small medieval cottage with a thatched roof" />
    <button type="submit">Search Exa</button>
  </form>
  <div id="status" class="muted"></div>
  <h2>Images</h2>
  <div id="images" class="grid"></div>
  <h2>Visual Descriptions</h2>
  <div id="descriptions"></div>
  <h2>Raw JSON</h2>
  <pre id="raw"></pre>
  <script>
    const form = document.querySelector("#form");
    const promptInput = document.querySelector("#prompt");
    const statusEl = document.querySelector("#status");
    const imagesEl = document.querySelector("#images");
    const descriptionsEl = document.querySelector("#descriptions");
    const rawEl = document.querySelector("#raw");

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      imagesEl.innerHTML = "";
      descriptionsEl.innerHTML = "";
      rawEl.textContent = "";
      statusEl.textContent = "Searching Exa...";
      statusEl.className = "muted";

      try {
        const prompt = encodeURIComponent(promptInput.value);
        const response = await fetch(`/debug/research?prompt=${prompt}`);
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
        const data = await response.json();
        statusEl.textContent = `cached=${data.cached}, descriptions=${data.visual_descriptions.length}, images=${data.images.length}`;

        imagesEl.innerHTML = data.images.map((image) => `
          <div class="card">
            <img src="${image.static_url}" alt="${image.description}" />
            <strong>${image.width}x${image.height}</strong>
            <p>${image.description}</p>
          </div>
        `).join("");

        descriptionsEl.innerHTML = data.visual_descriptions.map((item) => `
          <div class="card">
            <p>${item.description}</p>
          </div>
        `).join("");

        rawEl.textContent = JSON.stringify(data, null, 2);
      } catch (error) {
        statusEl.className = "error";
        statusEl.textContent = String(error);
      }
    });
  </script>
</body>
</html>
"""
