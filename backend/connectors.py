import numpy as np
import trimesh


class ConnectorError(ValueError):
    pass


def _plane_basis(normal):
    n = normal / np.linalg.norm(normal)
    helper = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(n, helper)) > 0.9:
        helper = np.array([1.0, 0.0, 0.0])
    u = np.cross(n, helper)
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    return u, v, n


def _row_positions(lo, hi, k, diameter, gap):
    span = hi - lo
    needed = k * diameter + (k - 1) * gap
    if needed > span:
        return None
    if k == 1:
        return [(lo + hi) / 2]
    step = (span - diameter) / (k - 1)
    return [lo + diameter / 2 + i * step for i in range(k)]


def compute_sites(piece, origin, normal, count, diameter):
    verts = piece.vertices
    dist = np.abs((verts - origin) @ normal)
    span = float(np.max(piece.extents))
    eps = span * 0.02
    near = verts[dist < eps]
    if len(near) < 4:
        raise ConnectorError("La cara de corte es demasiado chica para colocar conectores")

    u, v, n = _plane_basis(normal)
    pu = (near - origin) @ u
    pv = (near - origin) @ v
    margin = diameter / 2.0 + 1.5
    gap = diameter * 0.6
    lo_u, hi_u = float(pu.min()) + margin, float(pu.max()) - margin
    lo_v, hi_v = float(pv.min()) + margin, float(pv.max()) - margin
    wu, wv = hi_u - lo_u, hi_v - lo_v

    candidates = [
        (np.linspace(lo_v, hi_v, 1), _row_positions(lo_u, hi_u, count, diameter, gap)),
        (_row_positions(lo_v, hi_v, count, diameter, gap), np.linspace(lo_u, hi_u, 1)),
    ]
    cols = int(np.ceil(np.sqrt(count)))
    rows = int(np.ceil(count / cols))
    if cols > 1 and rows > 1:
        candidates.append(
            (
                _row_positions(lo_v, hi_v, rows, diameter, gap),
                _row_positions(lo_u, hi_u, cols, diameter, gap),
            )
        )

    for vs, us in candidates:
        if us is None or vs is None:
            continue
        sites = []
        for sv in vs:
            for su in us:
                if len(sites) < count:
                    sites.append(origin + su * u + sv * v)
        return sites

    raise ConnectorError(
        f"No entran {count} conectores de {diameter:.1f} mm en la cara útil "
        f"de {wu:.1f} x {wv:.1f} mm; probá menos cantidad o menor diámetro"
    )


def _pin_primitive(site, normal, kind, width, length, sections=48):
    axis = normal / np.linalg.norm(normal)
    center = site + axis * (length / 2.0)
    rot = trimesh.geometry.align_vectors([0, 0, 1], axis)
    if kind == "prism":
        m = trimesh.creation.box(extents=[width, width, length])
    else:
        m = trimesh.creation.cylinder(radius=width / 2.0, height=length, sections=sections)
    m.apply_transform(rot)
    m.apply_translation(center)
    return m


def apply_connector(piece_pin_side, piece_hole_side, origin, normal, sites,
                    kind, diameter, depth, clearance):
    embed = min(2.0, depth * 0.4)
    overshoot = 0.6
    pin_len = embed + depth * 0.85

    axis = normal / np.linalg.norm(normal)
    pin_meshes = []
    hole_meshes = []
    for s in sites:
        base_pin = s - axis * embed
        pin_meshes.append(_pin_primitive(base_pin, normal, kind, diameter, pin_len))
        base_hole = s
        hole_len = depth + overshoot
        hole_meshes.append(_pin_primitive(base_hole, normal, kind,
                                          diameter + 2 * clearance, hole_len))

    try:
        pin_added = trimesh.boolean.union([piece_pin_side] + pin_meshes, engine="manifold")
        hole_cut = trimesh.boolean.difference([piece_hole_side] + hole_meshes, engine="manifold")
    except Exception as exc:
        raise ConnectorError(f"Fallo el booleano del conector: {exc}") from exc

    if not pin_added.is_watertight or not hole_cut.is_watertight:
        raise ConnectorError("El resultado del conector no es estanco")
    info = {"embed_mm": round(float(embed), 2), "pin_len_mm": round(float(pin_len), 2)}
    return pin_added, hole_cut, info
