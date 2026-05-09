"""Round-trip tests for the RLE encoder/decoder."""
from __future__ import annotations

import random

from pipeline.encode import decode_rle_zyx, encode_rle_zyx
from storage.sample import _build_sample_grid, SAMPLE_SIZE


def _make_grid(size: tuple[int, int, int], filler: int = 0) -> list[list[list[int]]]:
    sx, sy, sz = size
    return [[[filler for _ in range(sz)] for _ in range(sy)] for _ in range(sx)]


def test_round_trip_all_zero():
    size = (4, 4, 4)
    grid = _make_grid(size, 0)
    encoded = encode_rle_zyx(grid, size)
    assert decode_rle_zyx(encoded, size) == grid


def test_round_trip_solid_block():
    size = (8, 3, 5)
    grid = _make_grid(size, 7)
    encoded = encode_rle_zyx(grid, size)
    assert decode_rle_zyx(encoded, size) == grid


def test_round_trip_long_run_split():
    size = (20, 20, 20)
    grid = _make_grid(size, 1)
    encoded = encode_rle_zyx(grid, size)
    assert decode_rle_zyx(encoded, size) == grid


def test_round_trip_random():
    rng = random.Random(42)
    size = (6, 6, 6)
    grid = [
        [[rng.randint(0, 5) for _ in range(size[2])] for _ in range(size[1])]
        for _ in range(size[0])
    ]
    encoded = encode_rle_zyx(grid, size)
    assert decode_rle_zyx(encoded, size) == grid


def test_round_trip_sample_house():
    grid = _build_sample_grid()
    encoded = encode_rle_zyx(grid, SAMPLE_SIZE)
    assert decode_rle_zyx(encoded, SAMPLE_SIZE) == grid
