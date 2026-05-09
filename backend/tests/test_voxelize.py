"""Tests for GLB voxelization."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import trimesh

from pipeline.voxelize import save_voxelized_mesh, voxelize_mesh


def _colored_box(path: Path, extents: tuple[float, float, float]) -> None:
    mesh = trimesh.creation.box(extents=extents)
    mesh.visual.vertex_colors = np.tile(np.asarray([[220, 40, 30, 255]], dtype=np.uint8), (len(mesh.vertices), 1))
    mesh.export(path)


def test_voxelize_mesh_fits_max_size_and_hits_limiting_axis(tmp_path: Path):
    model_path = tmp_path / "box.glb"
    _colored_box(model_path, (2.0, 1.0, 1.0))

    voxels = voxelize_mesh(model_path, (20, 20, 20))

    assert voxels.size[0] == 20
    assert voxels.size[1] <= 20
    assert voxels.size[2] <= 20
    assert voxels.filled.shape == voxels.size
    assert voxels.rgb.shape == (*voxels.size, 3)
    assert voxels.filled.any()
    assert int(voxels.rgb[voxels.filled][:, 0].mean()) > 150


def test_voxelize_mesh_saves_debug_artifact(tmp_path: Path):
    model_path = tmp_path / "box.glb"
    _colored_box(model_path, (1.0, 1.0, 1.0))
    voxels = voxelize_mesh(model_path, (8, 8, 8))

    artifact = tmp_path / "voxel_grid.npz"
    save_voxelized_mesh(voxels, artifact)

    assert artifact.exists()
    loaded = np.load(artifact)
    assert tuple(int(v) for v in loaded["size"]) == voxels.size
    assert loaded["filled"].shape == voxels.size


def test_voxelize_missing_mesh_errors(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        voxelize_mesh(tmp_path / "missing.glb", (16, 16, 16))
