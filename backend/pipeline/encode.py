"""Voxel-grid encoding: dense numpy/list grid -> RLE bytes -> base64 string.

Encoding format (versioned by the `encoding` field in the API response):

    "rle-z-y-x"
        Iterate the dense grid in z-major, then y, then x order:
            for z in range(size_z):
                for y in range(size_y):
                    for x in range(size_x):
                        emit(grid[x][y][z])
        The resulting byte stream is RLE'd as pairs of (count, palette_index)
        bytes, where count is in [1, 255]. Runs longer than 255 are split
        across multiple pairs. Each value is a uint8 palette index, so
        palettes are limited to 256 entries (more than enough for
        hand-built Minecraft palettes).

The encoder is pure-stdlib so the backend stays light and the frontend
mod can implement the matching decoder in a few lines of Java/Kotlin.
"""
from __future__ import annotations

import base64
from collections.abc import Sequence


Grid3D = Sequence[Sequence[Sequence[int]]]


def encode_rle_zyx(
    grid: Grid3D,
    size: tuple[int, int, int],
) -> str:
    """Encode a dense 3D grid (indexed [x][y][z]) to base64-RLE.

    Args:
        grid: indexable as grid[x][y][z], values are uint8 palette indices.
        size: (size_x, size_y, size_z).

    Returns:
        Base64 string of the RLE byte stream.
    """
    sx, sy, sz = size
    out = bytearray()
    run_value: int | None = None
    run_count = 0

    def flush() -> None:
        nonlocal run_value, run_count
        if run_value is None:
            return
        while run_count > 0:
            chunk = min(run_count, 255)
            out.append(chunk)
            out.append(run_value)
            run_count -= chunk

    for z in range(sz):
        for y in range(sy):
            for x in range(sx):
                v = int(grid[x][y][z]) & 0xFF
                if run_value is None:
                    run_value = v
                    run_count = 1
                elif v == run_value:
                    run_count += 1
                else:
                    flush()
                    run_value = v
                    run_count = 1
    flush()
    return base64.b64encode(bytes(out)).decode("ascii")


def decode_rle_zyx(
    encoded: str,
    size: tuple[int, int, int],
) -> list[list[list[int]]]:
    """Inverse of `encode_rle_zyx`. Mostly used by tests and example tooling.

    Returns a dense list-of-lists-of-lists indexable as grid[x][y][z].
    """
    sx, sy, sz = size
    raw = base64.b64decode(encoded)
    if len(raw) % 2 != 0:
        raise ValueError("RLE byte stream length must be even (pairs of count, value).")

    grid: list[list[list[int]]] = [
        [[0 for _ in range(sz)] for _ in range(sy)] for _ in range(sx)
    ]
    pos = 0
    total = sx * sy * sz
    for i in range(0, len(raw), 2):
        count = raw[i]
        value = raw[i + 1]
        for _ in range(count):
            if pos >= total:
                raise ValueError("RLE stream is longer than declared size.")
            z = pos // (sx * sy)
            rem = pos % (sx * sy)
            y = rem // sx
            x = rem % sx
            grid[x][y][z] = value
            pos += 1
    if pos != total:
        raise ValueError(
            f"RLE stream is shorter than declared size ({pos} of {total} voxels)."
        )
    return grid
