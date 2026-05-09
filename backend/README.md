# Minecraft AI Backend

Generative-AI backend that turns a text prompt into a Minecraft block structure. Sends back a compact JSON the frontend mod renders into the world.

This document is the **API contract** your frontend mod consumes. The backend's pipeline (Exa research, GPT-4o vision planning, Fal Flux image generation, Fal Trellis image-to-3D, voxelization, block-mapping) is invisible to you.

## Phase 1 status

The pipeline is **stubbed**: `POST /builds` accepts a real request, walks through the same status stages the real pipeline will, and after a few seconds returns a hard-coded sample response (a small 5x5x5 cottage). This lets the frontend be built and tested end-to-end before the real generative pipeline lands.

A frozen example is committed at [`examples/sample_response.json`](examples/sample_response.json) so the renderer can be developed without running the server at all.

---

## Run locally

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
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
  "preview_image_url": null
}
```

`hero_image_url` and `preview_image_url` are `null` in Phase 1; they'll point to `/static/...` PNGs once the real pipeline ships.

### `GET /healthz`

Returns `{ "status": "ok" }`.

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
- **Phase 3:** Real pipeline — Exa research → GPT-4o vision plan → Fal Flux hero image → Fal Trellis image-to-3D → voxelize → block map.
- **Phase 4:** LLM semantic block refinement, isometric preview render, hollow-shell mode.
- **Phase 5:** SQLite job store, disk caching, retries, Gemini & local fallbacks, structured logs.
