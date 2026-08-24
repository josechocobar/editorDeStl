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

    sites = connectors.compute_sites(low, high, origin, normal, count=2,
                                     diameter=6.0, depth=8.0)
    assert len(sites) == 2
    dist = np.linalg.norm(sites[0] - sites[1])
    assert dist >= 6.0
    for s in sites:
        assert abs(s[0]) < 18 and abs(s[1]) < 18
        assert abs(s[2]) < 1e-6
        assert connectors._contains(low, s - normal * 0.8)
        assert connectors._contains(high, s + normal * 4.0)

    pin_added, hole_cut, info = connectors.apply_connector(
        low, high, origin, normal, sites,
        kind="pin", diameter=6.0, depth=8.0, clearance=0.25)

    assert pin_added.is_watertight
    assert hole_cut.is_watertight
    assert abs(pin_added.volume) > abs(low.volume)
    assert abs(hole_cut.volume) < abs(high.volume)
    assert info["pin_len_mm"] == pytest.approx(2 + 8 * 0.85, abs=0.01)


def test_sites_return_fewer_when_spaced_out():
    box = trimesh.creation.box(extents=[40, 40, 20])
    low = trimesh.intersections.slice_mesh_plane(box, [0, 0, -1], [0, 0, 0], cap=True)
    high = trimesh.intersections.slice_mesh_plane(box, [0, 0, 1], [0, 0, 0], cap=True)
    origin = np.array([0.0, 0.0, 0.0])
    normal = np.array([0.0, 0.0, 1.0])
    sites = connectors.compute_sites(low, high, origin, normal,
                                     count=8, diameter=12.0, depth=8.0)
    assert 1 <= len(sites) < 8
    min_dist = 12.0 * 1.7
    for i, a in enumerate(sites):
        for b in sites[i + 1:]:
            assert np.linalg.norm(a - b) >= min_dist


def test_prism_connector_works():
    box = trimesh.creation.box(extents=[40, 40, 20])
    low = trimesh.intersections.slice_mesh_plane(box, [0, 0, -1], [0, 0, 0], cap=True)
    high = trimesh.intersections.slice_mesh_plane(box, [0, 0, 1], [0, 0, 0], cap=True)
    origin = np.array([0.0, 0.0, 0.0])
    normal = np.array([0.0, 0.0, 1.0])
    sites = connectors.compute_sites(low, high, origin, normal, count=3,
                                     diameter=8.0, depth=10.0)
    pin_added, hole_cut, _ = connectors.apply_connector(
        low, high, origin, normal, sites,
        kind="prism", diameter=8.0, depth=10.0, clearance=0.3)
    assert pin_added.is_watertight and hole_cut.is_watertight
    assert abs(hole_cut.volume) < abs(high.volume)


def test_connector_sites_inset_from_edges():
    box = trimesh.creation.box(extents=[40, 40, 20])
    low = trimesh.intersections.slice_mesh_plane(box, [0, 0, -1], [0, 0, 0], cap=True)
    high = trimesh.intersections.slice_mesh_plane(box, [0, 0, 1], [0, 0, 0], cap=True)
    origin = np.array([0.0, 0.0, 0.0])
    normal = np.array([0.0, 0.0, 1.0])
    sites = connectors.compute_sites(low, high, origin, normal, count=2,
                                     diameter=6.0, depth=8.0)
    assert len(sites) == 2
    limit = 20.0 - (6.0 / 2.0 + 1.2)
    for s in sites:
        assert abs(s[0]) <= limit + 1e-6 and abs(s[1]) <= limit + 1e-6


def test_connector_on_tiny_face_raises():
    tiny = trimesh.creation.box(extents=[6, 6, 30])
    low = trimesh.intersections.slice_mesh_plane(tiny, [0, 0, -1], [0, 0, 0], cap=True)
    high = trimesh.intersections.slice_mesh_plane(tiny, [0, 0, 1], [0, 0, 0], cap=True)
    origin = np.array([0.0, 0.0, 0.0])
    normal = np.array([0.0, 0.0, 1.0])
    with pytest.raises(connectors.ConnectorError):
        connectors.compute_sites(low, high, origin, normal, count=2,
                                 diameter=6.0, depth=8.0)


def _make_L():
    stem = trimesh.creation.box(extents=[15, 60, 20])
    stem.apply_translation([-12.5, 0, 0])
    foot = trimesh.creation.box(extents=[40, 15, 20])
    foot.apply_translation([0, -22.5, 0])
    return trimesh.boolean.union([stem, foot], engine="manifold")


def test_L_sites_only_on_shared_material():
    L = _make_L()
    pieces, splits = mesh_ops.cut_half(L, "x", 0.5)
    low, high = pieces[0], pieces[1]
    origin = np.array(splits[0]["origin"])
    normal = np.array(splits[0]["normal"])

    sites = connectors.compute_sites(low, high, origin, normal,
                                     count=4, diameter=6.0, depth=8.0)
    assert 1 <= len(sites) <= 4
    for s in sites:
        assert abs(s[0]) < 1e-6
        assert -26.8 < s[1] < -16.2
        assert connectors._contains(low, s - normal * 0.8)
        assert connectors._contains(high, s + normal * 4.0)


def test_L_smaller_pins_fit_more_sites():
    L = _make_L()
    pieces, splits = mesh_ops.cut_half(L, "x", 0.5)
    low, high = pieces[0], pieces[1]
    origin = np.array(splits[0]["origin"])
    normal = np.array(splits[0]["normal"])
    sites_big = connectors.compute_sites(low, high, origin, normal,
                                         count=4, diameter=6.0, depth=8.0)
    sites_small = connectors.compute_sites(low, high, origin, normal,
                                           count=4, diameter=3.0, depth=8.0)
    assert len(sites_small) > len(sites_big)
    min_dist = 3.0 * 1.7
    for i, a in enumerate(sites_small):
        for b in sites_small[i + 1:]:
            assert np.linalg.norm(a - b) >= min_dist


def test_L_end_to_end_no_floating_pins():
    L = _make_L()
    pieces, splits = mesh_ops.cut_half(L, "x", 0.5)
    low, high = pieces
    origin = np.array(splits[0]["origin"])
    normal = np.array(splits[0]["normal"])
    sites = connectors.compute_sites(low, high, origin, normal,
                                     count=2, diameter=6.0, depth=8.0)
    macho, hembra, info = connectors.apply_connector(
        low, high, origin, normal, sites,
        kind="pin", diameter=6.0, depth=8.0, clearance=0.25)
    assert macho.is_watertight and hembra.is_watertight
    assert abs(macho.volume) > abs(low.volume)
    assert abs(hembra.volume) < abs(high.volume)

    embed = info["embed_mm"]
    protrusion = info["pin_len_mm"] - embed
    for s in sites:
        assert connectors._contains(macho, s + normal * (protrusion * 0.5))
        assert not connectors._contains(macho, s + normal * (protrusion + 1.0))
        assert not connectors._contains(hembra, s + normal * 2.0)
        assert connectors._contains(hembra, s + normal * 9.5)


def test_split_multi_annular_section_box_with_hole():
    box = trimesh.creation.box(extents=[40, 40, 20])
    hole = trimesh.creation.cylinder(radius=8, height=30)
    bracket = trimesh.boolean.difference([box, hole], engine="manifold")
    pieces, splits = mesh_ops.split_multi(bracket, 4)
    assert len(pieces) >= 2
    assert all(p.is_watertight for p in pieces)
    total = sum(abs(p.volume) for p in pieces)
    assert total == pytest.approx(abs(bracket.volume), rel=1e-3)


def test_load_and_info_roundtrip(tmp_path):
    sphere = trimesh.creation.icosphere(subdivisions=2, radius=15)
    path = tmp_path / "sphere.stl"
    sphere.export(path)
    loaded = mesh_ops.load_mesh(path)
    info = mesh_ops.model_info(loaded)
    assert info["watertight"] is True
    assert info["triangles"] > 0
    assert all(d == pytest.approx(30.0, abs=0.5) for d in info["dims_mm"])


def test_decimate_reduces_and_preserves_shape():
    sphere = trimesh.creation.icosphere(subdivisions=4, radius=15)
    dec = mesh_ops.decimate_for_preview(sphere, target_tris=800)
    assert len(dec.faces) <= 900
    assert len(dec.faces) >= 100
    assert dec.is_watertight
    assert abs(dec.volume) == pytest.approx(abs(sphere.volume), rel=0.05)


def test_decimate_noop_below_target():
    box = trimesh.creation.box(extents=[10, 10, 10])
    out = mesh_ops.decimate_for_preview(box, target_tris=120_000)
    assert len(out.faces) == len(box.faces)


def test_suggest_box_mid_cut():
    box = trimesh.creation.box(extents=[40, 40, 20])
    origin = np.array([0.0, 0.0, 0.0])
    normal = np.array([0.0, 0.0, 1.0])
    sug = connectors.suggest(box, origin, normal)
    assert 3.0 <= sug["diameter_mm"] <= 6.5
    assert 3.0 <= sug["depth_mm"] <= 6.0
    assert 1 <= sug["count"] <= 4
    assert sug["thickness_mm"] == pytest.approx(10.0, abs=0.2)


def test_suggest_thin_wall_limits_diameter():
    thin = trimesh.creation.box(extents=[60, 60, 8])
    origin = np.array([0.0, 0.0, 0.0])
    normal = np.array([0.0, 0.0, 1.0])
    sug = connectors.suggest(thin, origin, normal)
    assert sug["thickness_mm"] == pytest.approx(4.0, abs=0.2)
    assert sug["diameter_mm"] <= 0.6 * sug["thickness_mm"]
    assert sug["depth_mm"] >= 3.0
