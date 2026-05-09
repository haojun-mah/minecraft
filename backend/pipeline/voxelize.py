"""Mesh voxelization for Minecraft block mapping."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import trimesh


@dataclass(frozen=True)
class VoxelizedMesh:
    size: tuple[int, int, int]
    filled: np.ndarray
    rgb: np.ndarray

    def __post_init__(self) -> None:
        if self.filled.shape != self.size:
            raise ValueError(f"filled shape {self.filled.shape} does not match size {self.size}")
        if self.rgb.shape != (*self.size, 3):
            raise ValueError(f"rgb shape {self.rgb.shape} does not match size {self.size} + RGB")


def voxelize_mesh(glb_path: Path, max_size: tuple[int, int, int]) -> VoxelizedMesh:
    """Load a mesh and voxelize it inside `max_size` while preserving aspect ratio."""
    if not glb_path.exists():
        raise FileNotFoundError(f"Mesh file does not exist: {glb_path}")
    mesh = _load_mesh(glb_path)
    extents = np.asarray(mesh.extents, dtype=np.float64)
    if extents.shape != (3,) or np.any(~np.isfinite(extents)) or np.any(extents <= 0):
        raise ValueError(f"Mesh has invalid extents: {extents.tolist()}")

    max_dims = np.asarray(max_size, dtype=np.int64)
    if max_dims.shape != (3,) or np.any(max_dims <= 0):
        raise ValueError(f"max_size must contain three positive integers: {max_size}")

    target_size = _target_size(extents, max_dims)
    pitch = float(np.min(extents / target_size))
    if not np.isfinite(pitch) or pitch <= 0:
        raise ValueError(f"Could not compute voxel pitch for {glb_path}")

    voxel_grid = mesh.voxelized(pitch)
    try:
        voxel_grid = voxel_grid.fill()
    except Exception:  # noqa: BLE001 - fill is best-effort only
        pass
    filled = np.asarray(voxel_grid.matrix, dtype=bool)
    if filled.size == 0 or not filled.any():
        raise ValueError(f"Voxelization produced no filled voxels: {glb_path}")

    filled = _resample_bool_grid(filled, tuple(int(v) for v in target_size))
    rgb = _sample_rgb(mesh, filled, extents)
    return VoxelizedMesh(size=tuple(int(v) for v in target_size), filled=filled, rgb=rgb)


def save_voxelized_mesh(voxels: VoxelizedMesh, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, size=np.asarray(voxels.size), filled=voxels.filled, rgb=voxels.rgb)


def _load_mesh(path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load(path, force="scene")
    if isinstance(loaded, trimesh.Scene):
        geometries = [
            geom
            for geom in loaded.geometry.values()
            if isinstance(geom, trimesh.Trimesh) and len(geom.vertices) > 0 and len(geom.faces) > 0
        ]
        if not geometries:
            raise ValueError(f"Scene contains no mesh geometry: {path}")
        mesh = trimesh.util.concatenate(geometries)
    elif isinstance(loaded, trimesh.Trimesh):
        mesh = loaded
    else:
        raise ValueError(f"Unsupported mesh type from {path}: {type(loaded)!r}")
    if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
        raise ValueError(f"Mesh has no geometry: {path}")
    mesh = mesh.copy()
    mesh.remove_unreferenced_vertices()
    return mesh


def _target_size(extents: np.ndarray, max_dims: np.ndarray) -> np.ndarray:
    scale = float(np.min(max_dims / extents))
    target = np.maximum(1, np.rint(extents * scale).astype(np.int64))
    target = np.minimum(target, max_dims)
    limiting_axis = int(np.argmin(max_dims / extents))
    target[limiting_axis] = max_dims[limiting_axis]
    return target


def _resample_bool_grid(grid: np.ndarray, target_size: tuple[int, int, int]) -> np.ndarray:
    if grid.shape == target_size:
        return grid.astype(bool, copy=False)
    axes = [
        np.clip(np.rint(np.linspace(0, grid.shape[axis] - 1, target_size[axis])).astype(int), 0, grid.shape[axis] - 1)
        for axis in range(3)
    ]
    return grid[np.ix_(axes[0], axes[1], axes[2])].astype(bool, copy=False)


def _sample_rgb(mesh: trimesh.Trimesh, filled: np.ndarray, extents: np.ndarray) -> np.ndarray:
    rgb = np.zeros((*filled.shape, 3), dtype=np.uint8)
    if not filled.any():
        return rgb

    default_color = _mesh_average_color(mesh)
    rgb[filled] = default_color

    vertex_colors = _vertex_colors(mesh)
    if vertex_colors is not None and len(vertex_colors) == len(mesh.vertices):
        centers = _filled_centers(mesh.bounds[0], extents, filled)
        colors = _nearest_colors(centers, np.asarray(mesh.vertices), vertex_colors)
        rgb[filled] = colors
        return rgb

    face_colors = _face_colors(mesh)
    if face_colors is not None and len(face_colors) == len(mesh.faces):
        centers = _filled_centers(mesh.bounds[0], extents, filled)
        face_centers = np.asarray(mesh.triangles_center)
        colors = _nearest_colors(centers, face_centers, face_colors)
        rgb[filled] = colors
    return rgb


def _filled_centers(bounds_min: np.ndarray, extents: np.ndarray, filled: np.ndarray) -> np.ndarray:
    coords = np.argwhere(filled).astype(np.float64)
    shape = np.asarray(filled.shape, dtype=np.float64)
    return bounds_min + ((coords + 0.5) / shape) * extents


def _nearest_colors(points: np.ndarray, color_points: np.ndarray, colors: np.ndarray) -> np.ndarray:
    if len(points) == 0 or len(color_points) == 0:
        return np.zeros((len(points), 3), dtype=np.uint8)
    output = np.empty((len(points), 3), dtype=np.uint8)
    chunk_size = 2048
    for start in range(0, len(points), chunk_size):
        chunk = points[start : start + chunk_size]
        distances = np.sum((chunk[:, None, :] - color_points[None, :, :]) ** 2, axis=2)
        nearest = np.argmin(distances, axis=1)
        output[start : start + len(chunk)] = colors[nearest]
    return output


def _vertex_colors(mesh: trimesh.Trimesh) -> np.ndarray | None:
    colors = getattr(mesh.visual, "vertex_colors", None)
    if colors is None or len(colors) == 0:
        return None
    return np.asarray(colors[:, :3], dtype=np.uint8)


def _face_colors(mesh: trimesh.Trimesh) -> np.ndarray | None:
    colors = getattr(mesh.visual, "face_colors", None)
    if colors is None or len(colors) == 0:
        return None
    return np.asarray(colors[:, :3], dtype=np.uint8)


def _mesh_average_color(mesh: trimesh.Trimesh) -> np.ndarray:
    vertex_colors = _vertex_colors(mesh)
    if vertex_colors is not None and len(vertex_colors) > 0:
        return np.mean(vertex_colors, axis=0).astype(np.uint8)
    face_colors = _face_colors(mesh)
    if face_colors is not None and len(face_colors) > 0:
        return np.mean(face_colors, axis=0).astype(np.uint8)
    return np.asarray([160, 160, 160], dtype=np.uint8)
