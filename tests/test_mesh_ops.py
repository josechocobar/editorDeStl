import numpy as np
import pytest
import trimesh

from backend import connectors, mesh_ops


def test_cut_half_box_two_watertight_pieces():
    box = trimesh.creation.box(extents=[20, 10, 30])
    pieces, splits = mesh_ops.cut_half(box, "z", 0.5)
    assert len(pieces) == 2
    assert all(p.is_watertight for p in pieces)
    total = sum(abs(p.volume) for p in pieces)
    assert total == pytest.approx(abs(box.volume), rel=1e-3)
    assert splits[0]["a_index"] == 0 and splits[0]["b_index"] == 1


def test_cut_half_position_controls_ratio():
    box = trimesh.creation.box(extents=[20, 10, 30])
    pieces, _ = mesh_ops.cut_half(box, "z", 0.75)
    vols = sorted(abs(p.volume) for p in pieces)
    assert vols[1] / (vols[0] + vols[1]) == pytest.approx(0.75, abs=1e-3)


def test_cut_half_invalid_position_raises():
    box = trimesh.creation.box(extents=[20, 10, 30])
    with pytest.raises(ValueError):
        mesh_ops.cut_half(box, "z", 1.5)


def test_cut_half_plane_through_air_raises():
    big = trimesh.creation.icosphere(subdivisions=3, radius=15)
    big.apply_translation([-20, 0, 0])
    tiny = trimesh.creation.icosphere(subdivisions=2, radius=0.5)
    tiny.apply_translation([25, 0, 0])
    pair = trimesh.boolean.union([big, tiny], engine="manifold")
    with pytest.raises(ValueError):
        mesh_ops.cut_half(pair, "x", 0.55)


def test_split_multi_sphere_four_parts():
    sphere = trimesh.creation.icosphere(subdivisions=3, radius=15)
    pieces, splits = mesh_ops.split_multi(sphere, 4)
    assert len(pieces) == 4
    assert len(splits) == 3
    assert all(p.is_watertight for p in pieces)
    total = sum(abs(p.volume) for p in pieces)
    assert total == pytest.approx(abs(sphere.volume), rel=1e-3)


def test_pin_connector_watertight_and_fits():
    box = trimesh.creation.box(extents=[40, 40, 20])
    low = trimesh.intersections.slice_mesh_plane(
        box, [0, 0, -1], [0, 0, 0], cap=True)
    high = trimesh.intersections.slice_mesh_plane(
        box, [0, 0, 1], [0, 0, 0], cap=True)
    origin = np.array([0.0, 0.0, 0.0])
    normal = np.array([0.0, 0.0, 1.0])

    sites = connectors.compute_sites(high, origin, normal, count=2,
                                     diameter=6.0)
    assert len(sites) == 2
    for s in sites:
        assert abs(s[0]) < 18 and abs(s[1]) < 18
        assert abs(s[2]) < 1e-6

    pin_added, hole_cut, info = connectors.apply_connector(
        low, high, origin, normal, sites,
        kind="pin", diameter=6.0, depth=8.0, clearance=0.25)

    assert pin_added.is_watertight
    assert hole_cut.is_watertight
    assert abs(pin_added.volume) > abs(low.volume)
    assert abs(hole_cut.volume) < abs(high.volume)
    assert info["pin_len_mm"] == pytest.approx(2 + 8 * 0.85, abs=0.01)


def test_prism_connector_works():
    box = trimesh.creation.box(extents=[40, 40, 20])
    low = trimesh.intersections.slice_mesh_plane(box, [0, 0, -1], [0, 0, 0], cap=True)
    high = trimesh.intersections.slice_mesh_plane(box, [0, 0, 1], [0, 0, 0], cap=True)
    origin = np.array([0.0, 0.0, 0.0])
    normal = np.array([0.0, 0.0, 1.0])
    sites = connectors.compute_sites(low, origin, normal, count=3, diameter=8.0)
    pin_added, hole_cut, _ = connectors.apply_connector(
        low, high, origin, normal, sites,
        kind="prism", diameter=8.0, depth=10.0, clearance=0.3)
    assert pin_added.is_watertight and hole_cut.is_watertight
    assert abs(hole_cut.volume) < abs(high.volume)


def test_connector_on_tiny_face_raises():
    tiny = trimesh.creation.box(extents=[6, 6, 30])
    half = trimesh.intersections.slice_mesh_plane(tiny, [0, 0, -1], [0, 0, 0], cap=True)
    origin = np.array([0.0, 0.0, 0.0])
    normal = np.array([0.0, 0.0, 1.0])
    with pytest.raises(connectors.ConnectorError):
        connectors.compute_sites(half, origin, normal, count=2, diameter=6.0)


def test_load_and_info_roundtrip(tmp_path):
    sphere = trimesh.creation.icosphere(subdivisions=2, radius=15)
    path = tmp_path / "sphere.stl"
    sphere.export(path)
    loaded = mesh_ops.load_mesh(path)
    info = mesh_ops.model_info(loaded)
    assert info["watertight"] is True
    assert info["triangles"] > 0
    assert all(d == pytest.approx(30.0, abs=0.5) for d in info["dims_mm"])
