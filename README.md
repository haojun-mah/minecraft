# AI Architect for Minecraft

AI Architect is a Minecraft mod plus a Python backend that turns a natural-language building prompt into a structure you can preview and place in-game.

Press `G`, describe a build, choose where it should go, preview the shape as a ghost outline, then place it block by block into the world.

## What It Can Do

- Generate a build from a text prompt through the backend API.
- Preview the generated structure in-world before placing it.
- Reposition the preview by changing coordinates or dragging it with the crosshair after closing the UI.
- Place blocks progressively with live progress updates.
- Expose backend endpoints for queued builds, image-based builds, status polling, and a frontend-friendly synchronous generate route.

## Current State

- The end-to-end frontend/backend integration is in place.
- The mod currently uses `POST /generate` and expects a flat block list like `{x, y, z, block}`.
- The backend pipeline is still stubbed for Phase 1. It walks through realistic pipeline stages, then returns a deterministic sample cottage shape.
- The backend also has richer async APIs under `/builds` and `/builds/from-image`, but the in-game UI is currently wired to the text-prompt flow.

## Project Layout

- `src/` Fabric mod sources for the Minecraft client/server integration.
- `backend/` FastAPI backend, pipeline orchestration, sample data, and tests.
- `backend/examples/sample_response.json` Frontend-ready sample block list you can use without running the server.

## Requirements

- Java 25 for the Minecraft mod toolchain in this repo.
- Python 3.11+ for the backend.

## Run The Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Useful endpoints:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/healthz`
- `http://127.0.0.1:8000/generate`

By default, the mod looks for the backend at `http://127.0.0.1:8000`.

You can override that with either:

- JVM property: `-Dmodid.backendUrl=http://host:port`
- Environment variable: `MINECRAFT_AI_BACKEND_URL=http://host:port`

## Run The Mod

From the repo root:

```bash
./gradlew runClient
```

Then in-game:

1. Press `G` to open AI Architect.
2. Enter a build prompt.
3. Set the target `X/Y/Z`.
4. Click `Preview` to inspect the shape.
5. Click `Place` to build it in the world.

## Backend API Summary

The backend exposes two styles of API:

- `POST /generate`
  Returns a flat block list for the mod UI. This is the path the frontend uses now.
- `POST /builds` and `GET /builds/{job_id}`
  Async job flow for structured build requests and polling.
- `POST /builds/from-image`
  Async image upload flow for image-conditioned builds.

## Notes

- The checked-in sample response is already in the flat block-list format the frontend can consume directly.
- Generated placement currently happens block by block so players can see progress rather than having the structure appear instantly.
- Some backend files currently contain unresolved merge markers. This README reflects the intended integrated behavior and the active frontend path, not every conflicting branch variant.

## License

This repository started from the Fabric example mod template, which is available under CC0. Check repository files before publishing or redistributing under a different license model.
