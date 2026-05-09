"""Typed output from the Exa research stage."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class VisualDescription(BaseModel):
    description: str


class ReferenceImage(BaseModel):
    path: Path
    width: int
    height: int
    static_url: str
    description: str


class ResearchBundle(BaseModel):
    prompt: str
    visual_descriptions: list[VisualDescription] = Field(default_factory=list)
    images: list[ReferenceImage] = Field(default_factory=list)
    cached: bool = False
    manifest_path: Path | None = None
