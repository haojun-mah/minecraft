"""Protocols for hero-image generators."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ImageGenerator(Protocol):
    async def generate(
        self,
        *,
        prompt: str,
        output_dir: Path,
        size: str,
        candidate_count: int = 1,
    ) -> Path:
        """Generate a hero image and return the saved file path."""
