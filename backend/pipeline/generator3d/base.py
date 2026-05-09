"""Protocols for image-to-3D generators."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Generator3D(Protocol):
    async def generate(
        self,
        *,
        image: Path,
        output_dir: Path,
        seed: int | None = None,
    ) -> Path:
        """Generate a 3D model and return the saved GLB path."""
