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


def _contains(mesh, point):
    try:
        return bool(mesh.contains([point])[0])
    except Exception:
        return False


def compute_sites(piece_male, piece_female, origin, normal, count, diameter, depth=8.0):
    dist = np.abs((piece_male.vertices - origin) @ normal)
    span = float(np.max(piece_male.extents))
    eps = span * 0.02
    near = piece_male.vertices[dist < eps]
    if len(near) < 3:
        raise ConnectorError("La cara de corte es demasiado chica para colocar conectores")

    u, v, n = _plane_basis(normal)
    pu = (near - origin) @ u
    pv = (near - origin) @ v
    margin = diameter / 2.0 + 1.2
    lo_u, hi_u = float(pu.min()) + margin, float(pu.max()) - margin
    lo_v, hi_v = float(pv.min()) + margin, float(pv.max()) - margin

    embed = min(2.0, depth * 0.4)
    step = max(diameter * 1.25, 1.0)

    def axis_points(lo, hi):
        span = hi - lo
        if hi <= lo:
            return []
        if span <= diameter:
            return [(lo + hi) / 2]
        k = int(span // step) + 1
        return [float(x) for x in np.linspace(lo + diameter / 2,
                                              hi - diameter / 2, k)]

    su_vals = axis_points(lo_u, hi_u)
    sv_vals = axis_points(lo_v, hi_v)
    if not su_vals or not sv_vals:
        raise ConnectorError(
            f"No entra un conector de {diameter:.1f} mm en la cara útil de "
            f"{hi_u - lo_u:.1f} x {hi_v - lo_v:.1f} mm"
        )

    valid = []
    for sv in sv_vals:
        for su in su_vals:
            base = origin + su * u + sv * v
            probe_male = base - n * (embed * 0.5)
            probe_female = base + n * (depth * 0.5)
            if _contains(piece_male, probe_male) and _contains(piece_female, probe_female):
                valid.append(base)

    min_dist = diameter * 1.7
    chosen = []
    for cand in valid:
        if all(float(np.linalg.norm(cand - c)) >= min_dist for c in chosen):
            chosen.append(cand)
            if len(chosen) >= count:
                break

    if not chosen:
        raise ConnectorError(
            f"Ningún punto de la cara de corte tiene material en ambas piezas "
            f"para un conector de {diameter:.1f} mm"
        )
    return chosen


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
