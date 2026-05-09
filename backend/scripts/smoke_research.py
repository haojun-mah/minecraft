"""Run the Exa research stage once against the real API.

Usage:
    python -m scripts.smoke_research "a medieval cottage"
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import get_settings  # noqa: E402
from pipeline.research import research  # noqa: E402


async def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", help="Prompt to research with Exa")
    parser.add_argument(
        "--job-id",
        default="smoke",
        help="Artifact folder name under ARTIFACTS_DIR (default: smoke)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full ResearchBundle as JSON.",
    )
    args = parser.parse_args()

    settings = get_settings()
    bundle = await research(
        args.prompt,
        job_id=args.job_id,
        artifacts_dir=settings.artifacts_dir,
        settings=settings,
    )

    if args.json:
        print(json.dumps(bundle.model_dump(mode="json"), indent=2))
        return 0 if settings.exa_api_key else 1

    print(f"prompt: {bundle.prompt}")
    print(f"cached: {bundle.cached}")
    print(f"visual descriptions: {len(bundle.visual_descriptions)}")
    for index, item in enumerate(bundle.visual_descriptions, start=1):
        print(f"\n[{index}] {item.description}")

    print(f"\nimages: {len(bundle.images)}")
    for image in bundle.images:
        print(f"- {image.path} ({image.width}x{image.height})")
        print(f"  {image.description}")

    if not settings.exa_api_key:
        print("\nEXA_API_KEY is not set, so this smoke run returned an empty bundle.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
