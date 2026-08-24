import numpy as np
import pytest
import trimesh

from backend import supports

SPEC = {
    "angle": 50.0,
    "tip_diameter": 0.8,
    "contact_diameter": 0.5,
    "spacing": 1.8,
    "z_gap": 0.2,
    "base_thickness": 1.2,
}


def _t_piece():
    """Columna con travesaño: genera voladizo real sobre aire."""
    pillar = trimesh.creation.box(extents=[10, 10, 30])
    pillar.apply_translation([0, 0, 15])
    bar = trimesh.creation.box(extents=[44, 10, 6])
    bar.apply_translation([0, 0, 27])
    return trimesh.boolean.union([pillar, bar], engine="manifold")


def test_overhang_piece_gets_supports_and_base():
    piece = _t_piece()
    out, info = supports.add_supports(piece, SPEC)
    assert info["tips"] > 0
    assert info["branches"] > 0
    assert info["added_volume_cm3"] > 0
    assert out.is_watertight
    assert out.bounds[0][2] == pytest.approx(piece.bounds[0][2], abs=1e-6)
    assert out.bounds[1][2] == pytest.approx(piece.bounds[1][2], abs=1e-3)


def test_no_overhangs_returns_piece_unchanged():
    cube = trimesh.creation.box(extents=[20, 20, 20])
    out, info = supports.add_supports(cube, SPEC)
    assert info["tips"] == 0
    assert info["added_volume_cm3"] == 0.0
    assert len(out.faces) == len(cube.faces)
    assert abs(out.volume) == pytest.approx(abs(cube.volume))


def test_sphere_contacts_only_on_lower_half():
    sphere = trimesh.creation.icosphere(subdivisions=3, radius=12)
    sphere.apply_translation([0, 0, 20])
    pts = supports.find_contact_points(sphere, SPEC["angle"], SPEC["spacing"])
    assert len(pts) >= 5
    assert all(p[2] <= 22.0 for p in pts)


def test_higher_angle_threshold_finds_fewer_contacts():
    sphere = trimesh.creation.icosphere(subdivisions=3, radius=12)
    sphere.apply_translation([0, 0, 20])
    shallow = supports.find_contact_points(sphere, 30.0, SPEC["spacing"])
    steep = supports.find_contact_points(sphere, 70.0, SPEC["spacing"])
    assert len(shallow) > len(steep) >= 0


def test_sphere_supported_watertight_and_contains_original():
    sphere = trimesh.creation.icosphere(subdivisions=3, radius=12)
    sphere.apply_translation([0, 0, 20])
    out, info = supports.add_supports(sphere, SPEC)
    assert info["tips"] > 0
    assert out.is_watertight
    assert abs(out.volume) > abs(sphere.volume)
    assert bool(np.all(out.bounds[0] <= sphere.bounds[0] + 1e-6))
    assert bool(np.all(out.bounds[1] >= sphere.bounds[1] - 1e-6))


def test_pad_sits_on_piece_floor_even_with_low_contacts():
    """El pad se ancla al min-z de la pieza, no al pie de columna más bajo
    (contactos cercanos al polo inferior tiraban la base por debajo)."""
    sphere = trimesh.creation.icosphere(subdivisions=3, radius=12)
    sphere.apply_translation([0, 0, 20])
    out, info = supports.add_supports(sphere, SPEC)
    assert info["tips"] > 0
    assert out.bounds[0][2] == pytest.approx(sphere.bounds[0][2], abs=1e-6)


def test_base_thickness_is_honored():
    piece = _t_piece()
    thick = dict(SPEC, base_thickness=3.0)
    out, _ = supports.add_supports(piece, thick)
    assert out.is_watertight
    assert abs(out.volume) > abs(
        supports.add_supports(_t_piece(), SPEC)[0].volume)


def test_generation_is_deterministic():
    a, ia = supports.add_supports(_t_piece(), SPEC)
    b, ib = supports.add_supports(_t_piece(), SPEC)
    assert len(a.vertices) == len(b.vertices)
    assert ia["tips"] == ib["tips"]
    assert ia["added_volume_cm3"] == ib["added_volume_cm3"]


def test_tapered_segment_is_valid_solid():
    seg = supports._tapered_segment([0, 0, 20], 0.4, [3, 1, 5], 1.2)
    assert seg is not None
    assert seg.is_watertight
    assert seg.volume > 0


def test_resting_on_model_skips_pad():
    pillar = trimesh.creation.box(extents=[10, 10, 30])
    slab = trimesh.creation.box(extents=[40, 40, 6])
    slab.apply_translation([0, 0, 33])
    lshape = trimesh.boolean.union([pillar, slab], engine="manifold")
    out, info = supports.add_supports(lshape, SPEC)
    assert out.is_watertight
    assert info["tips"] > 0
    assert abs(out.volume) > abs(lshape.volume)
