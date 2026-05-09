# Minecraft AI Backend

Generative-AI backend that turns a text prompt or an uploaded image into a Minecraft block structure. Sends back a compact JSON the frontend mod renders into the world.

This document is the **API contract** your frontend mod consumes. The backend's pipeline (Exa research, GPT-4o vision planning, OpenAI GPT Image hero generation, Fal Trellis image-to-3D, voxelization, block-mapping) is invisible to you.

## Phase 1 status

The pipeline is **stubbed**: `POST /builds` accepts a real request, walks through the same status stages the real pipeline will, and after a few seconds returns a hard-coded sample response (a small 5x5x5 cottage). `POST /builds/from-image` does the same thing for an uploaded image and stores the upload under `artifacts/` so the frontend can show it immediately. This lets the frontend be built and tested end-to-end before the real generative pipeline lands.

A frozen example is committed at [`examples/sample_response.json`](examples/sample_response.json) so the renderer can be developed without running the server at all.

---

## Run locally

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[pipeline,dev]"
cp .env.example .env

uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Visit:
- `http://127.0.0.1:8000/docs` — interactive OpenAPI docs
- `http://127.0.0.1:8000/healthz` — liveness probe

To share the local backend with a teammate on a different machine, expose the port with [ngrok](https://ngrok.com/):

```bash
ngrok http 8000
```

Use the resulting `https://*.ngrok-free.app` URL as the backend base URL in the mod.

---

## API

Base URL: `http://127.0.0.1:8000` (local) or your ngrok URL.

### `POST /builds`

Enqueue a build job. Returns immediately with a `job_id`.

Request:
```json
{
  "prompt": "a small medieval cottage with a thatched roof",
  "max_size": [48, 48, 48],
  "style_hint": "blocky low-poly",
  "seed": 42
}
```

Response (`202 Accepted`):
```json
{ "job_id": "j_abc123", "status": "queued" }
```

### `POST /builds/from-image`

Upload an image as `multipart/form-data`. `prompt` is optional and can be used as a hint for naming or logging.

Form fields:
- `image` — required file upload
- `prompt` — optional text hint
- `style_hint` — optional text hint
- `seed` — optional integer seed
- `max_size` — optional JSON array string like `[48,48,48]`

Response (`202 Accepted`):
```json
{ "job_id": "j_abc123", "status": "queued" }
```

### `GET /builds/{job_id}`

Poll for status. While running, you get progress updates:
```json
{
  "job_id": "j_abc123",
  "status": "running",
  "stage": "image_to_3d",
  "progress": 0.65,
  "error": null
}
```

`stage` is one of: `queued`, `research`, `planning`, `image_gen`, `image_to_3d`, `voxelizing`, `block_mapping`, `encoding`, `done`.

When `status == "done"`, the response is the **final build result**:

```json
{
  "job_id": "j_abc123",
  "status": "done",
  "prompt": "a small medieval cottage with a thatched roof",
  "size": [5, 5, 5],
  "origin": [0, 0, 0],
  "palette": [
    "minecraft:air",
    "minecraft:cobblestone",
    "minecraft:oak_planks",
    "minecraft:hay_block"
  ],
  "blocks": "BASE64_STRING",
  "encoding": "rle-z-y-x",
  "hero_image_url": null,
  "preview_image_url": null,
  "input_image_url": null
}
```

For text builds, `hero_image_url` points at the generated hero image under `/static/...`; the frozen sample response keeps it `null` so the example payload stays deterministic.
For image uploads, `input_image_url` points at the saved source image under `/static/...`, and `hero_image_url` currently reuses that same static URL in the stub so the frontend can preview the upload immediately.

### `GET /healthz`

Returns `{ "status": "ok" }`.

### `GET /debug/research?prompt=...`

Runs only the Exa research stage and returns the machine-readable research bundle. This is for backend debugging and for the next pipeline agent to verify the research output before wiring GPT/OpenAI image generation.

```bash
curl "http://127.0.0.1:8000/debug/research?prompt=a%20medieval%20cottage" | jq
```

Browser UI:

```text
http://127.0.0.1:8000/debug/research-ui
```

The response intentionally does **not** expose source websites. It returns architectural visual descriptions and locally saved reference images:

```json
{
  "prompt": "a medieval cottage",
  "visual_descriptions": [
    {
      "description": "Architectural visual detail: steep thatched roof, timber framing, stone base..."
    }
  ],
  "images": [
    {
      "path": "artifacts/j_abc123/refs/ref_0.jpg",
      "width": 1024,
      "height": 768,
      "static_url": "/static/j_abc123/refs/ref_0.jpg",
      "description": "Architectural visual detail: timber walls, straw roof, small window openings..."
    }
  ],
  "cached": false,
  "manifest_path": "artifacts/j_abc123/research_bundle.json"
}
```

### Errors

- `404 Not Found` — unknown `job_id`.
- `422 Unprocessable Entity` — validation error on the request body.
- A successful `GET /builds/{id}` may have `status: "error"` with a non-null `error` string if the pipeline failed.

---

## Decoding the `blocks` field

`blocks` is a **base64-encoded run-length-encoded byte stream** over the dense voxel grid. The format is intentionally trivial so it takes ~30 lines of code to decode in any language.

### Algorithm

1. `bytes = base64Decode(blocks)`
2. The bytes are pairs of `(count, palette_index)`, each one byte.
3. Iterate the dense grid in **z-major, then y, then x order**:
   ```
   for z in 0..size_z-1:
     for y in 0..size_y-1:
       for x in 0..size_x-1:
         grid[x][y][z] = nextValueFromRLE()
   ```
4. The resulting `grid[x][y][z]` is an index into `palette[]`, which gives you the Minecraft block ID (`"minecraft:air"`, `"minecraft:cobblestone"`, etc.).
5. `origin` is an optional offset relative to the player-chosen build location — start placing at `(player.x + origin.x, player.y + origin.y, player.z + origin.z)`.
6. Skip placing `"minecraft:air"` blocks (the receiver should not destroy existing blocks unless you decide to).

### Reference Java decoder

```java
import java.util.Base64;

static int[][][] decode(String blocksB64, int sizeX, int sizeY, int sizeZ) {
    byte[] raw = Base64.getDecoder().decode(blocksB64);
    int[][][] grid = new int[sizeX][sizeY][sizeZ];
    int pos = 0;
    int total = sizeX * sizeY * sizeZ;
    for (int i = 0; i < raw.length; i += 2) {
        int count = raw[i] & 0xFF;
        int value = raw[i + 1] & 0xFF;
        for (int n = 0; n < count; n++) {
            int z = pos / (sizeX * sizeY);
            int rem = pos % (sizeX * sizeY);
            int y = rem / sizeX;
            int x = rem % sizeX;
            grid[x][y][z] = value;
            pos++;
        }
    }
    if (pos != total) throw new IllegalStateException("RLE size mismatch");
    return grid;
}
```

### Reference Python decoder (also used in tests)

See [`pipeline/encode.py`](pipeline/encode.py) `decode_rle_zyx`.

---

## Research Handoff To GPT / Image Generation

The best handoff format is **JSON, not Markdown**.

Use Markdown only as a human debug artifact if needed. The actual pipeline should pass structured data from `research_bundle.json` into the next stage because JSON is stable, typed, and easy for another agent or Python module to load without parsing prose.

### Fixed artifact layout

For every text build job, Exa research writes deterministic per-job files:

```text
artifacts/{job_id}/research_bundle.json
artifacts/{job_id}/refs/ref_0.jpg
artifacts/{job_id}/refs/ref_1.jpg
artifacts/{job_id}/refs/ref_2.jpg
artifacts/{job_id}/refs/ref_3.jpg
```

There is no timestamp in the file names. Later stages can reliably pick up the manifest by `job_id`.

### Python handoff contract

The next stage should load the bundle through the helper:

```python
from pipeline.research import load_research_bundle

bundle = load_research_bundle(
    artifacts_dir=artifacts_dir,
    job_id=job_id,
)

descriptions = [item.description for item in bundle.visual_descriptions]
image_paths = [image.path for image in bundle.images]
```

The data model is:

```python
class ResearchBundle(BaseModel):
    prompt: str
    visual_descriptions: list[VisualDescription]
    images: list[ReferenceImage]
    cached: bool
    manifest_path: Path | None

class ReferenceImage(BaseModel):
    path: Path
    width: int
    height: int
    static_url: str
    description: str
```

### Recommended OpenAI image-generation prompt assembly

The next agent should build a single image-generation prompt from:

1. The user's original `bundle.prompt`
2. The architectural visual descriptions
3. A strict instruction to produce one clean hero image for image-to-3D

Recommended template:

```text
Create a single clean reference image for image-to-3D generation.

Subject:
{bundle.prompt}

Architectural visual details:
- {bundle.visual_descriptions[0].description}
- {bundle.visual_descriptions[1].description}
- ...

Image requirements:
- single complete subject
- three-quarter exterior view
- plain white or transparent background
- even studio lighting
- no people
- no text, labels, watermark, UI, or collage
- show the full silhouette
- emphasize roof, walls, doors, windows, proportions, materials, and decorative trim
- blocky, readable shapes suitable for Minecraft voxelization
```

If using a multimodal model before image generation, pass `bundle.images[*].path` as reference images and the same text above as context. If using a text-only image model, pass only the assembled prompt.

### Why not Markdown?

Markdown is useful for humans, but it is a poor machine contract:

- another stage has to parse bullets/headings from prose
- image paths are easier to lose or rename
- tests cannot validate the fields cleanly
- future fields like `preferred_blocks`, `style`, or `quality_score` become awkward

Use `research_bundle.json` as the source of truth. A Markdown summary can be generated later for debugging, but downstream stages should not depend on it.

---

## End-to-end smoke test

```bash
# Start the server in one terminal:
uvicorn main:app --reload --port 8000

# In another terminal:
curl -s -X POST http://127.0.0.1:8000/builds \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"a small medieval cottage"}'
# -> {"job_id":"j_xyz","status":"queued"}

# Poll until done (stub takes ~3 seconds):
curl -s http://127.0.0.1:8000/builds/j_xyz | jq .
```

You can also use `examples/sample_response.json` directly to develop the renderer without running the server.

---

## Re-freezing the sample response

If you change the sample shape or palette in [`storage/sample.py`](storage/sample.py), regenerate the example file:

```bash
python -m scripts.freeze_sample
```

---

## Tests

```bash
pytest
```

Round-trip tests cover the RLE encoder/decoder (including runs longer than 255, the sample house, and random grids).

---

## Roadmap

See the project plan for the full pipeline and phasing. Short version:

- **Phase 1 (current):** Stubbed pipeline, real API contract, sample response, decoder docs.
- **Phase 2:** OpenAI structured-output direct block generation (no 3D model).
- **Phase 3:** Real pipeline — Exa research → GPT-4o vision plan → OpenAI GPT Image hero image → Fal Trellis image-to-3D → voxelize → block map.
- **Phase 4:** LLM semantic block refinement, isometric preview render, hollow-shell mode.
- **Phase 5:** SQLite job store, disk caching, retries, Gemini & local fallbacks, structured logs.
