"""Generate frontend-ready `examples/sample_response.json` from the sample builder.

Run from the backend/ directory:
    python -m scripts.freeze_sample
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow `python scripts/freeze_sample.py` from anywhere.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from storage.sample import build_sample_flat_blocks  # noqa: E402


def main() -> None:
    result = build_sample_flat_blocks()
    out_path = ROOT / "examples" / "sample_response.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
