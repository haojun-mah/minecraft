"""Generate one OpenAI hero image for a house prompt using Exa research context.

Usage:
    python -m scripts.smoke_house_image
    python -m scripts.smoke_house_image "a small oak house with a red roof"
"""
from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import get_settings  # noqa: E402
from pipeline.image_gen.openai_image import (  # noqa: E402
    OpenAIImageGenerator,
    build_hero_prompt,
    choose_hero_image_size,
)
from pipeline.research import research  # noqa: E402


DEFAULT_PROMPT = "a cozy medieval house with timber framing, stone chimney, and thatched roof"
DEFAULT_MAX_SIZE = (48, 48, 48)


async def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "prompt",
        nargs="?",
        default=DEFAULT_PROMPT,
        help=f"House prompt to generate (default: {DEFAULT_PROMPT!r})",
    )
    parser.add_argument(
        "--style-hint",
        default="Minecraft-friendly blocky architectural concept",
        help="Optional style hint added to the OpenAI image prompt.",
    )
    parser.add_argument(
        "--job-id",
        default="house_smoke_" + secrets.token_urlsafe(6),
        help="Artifact folder name under ARTIFACTS_DIR.",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.openai_api_key:
        print("OPENAI_API_KEY is required to generate the hero image.")
        return 1

    bundle = await research(
        args.prompt,
        job_id=args.job_id,
        artifacts_dir=settings.artifacts_dir,
        settings=settings,
    )
    generator = OpenAIImageGenerator(settings=settings)
    job_dir = settings.artifacts_dir / args.job_id
    hero_path = await generator.generate(
        prompt=build_hero_prompt(args.prompt, args.style_hint, bundle),
        output_dir=job_dir,
        size=choose_hero_image_size(DEFAULT_MAX_SIZE),
        candidate_count=settings.openai_image_candidate_count,
    )

    print(f"prompt: {args.prompt}")
    print(f"job_id: {args.job_id}")
    print(f"research manifest: {job_dir / 'research_bundle.json'}")
    print(f"generated image: {hero_path}")
    print(f"static path: /static/{args.job_id}/{hero_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
