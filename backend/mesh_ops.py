import numpy as np
import trimesh

AXES = {"x": 0, "y": 1, "z": 2}
MIN_FACE_RATIO = 0.01


def load_mesh(path):
    loaded = trimesh.load_mesh(path, force="mesh")
    if not isinstance(loaded, trimesh.Trimesh) or len(loaded.faces) == 0:
        raise ValueError("El archivo no contiene una malla de triángulos válida")
    return loaded


def model_info(mesh):
    lo, hi = mesh.bounds
    extents = hi - lo
    return {
        "dims_mm": [round(float(e), 2) for e in extents],
        "volume_cm3": round(abs(mesh.volume) / 1000.0, 2),
        "triangles": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "center_mm": [round(float(c), 2) for c in (lo + hi) / 2.0],
    }


PREVIEW_MAX_TRIS = 120_000


def decimate_for_preview(mesh, target_tris=PREVIEW_MAX_TRIS):
    if len(mesh.faces) <= target_tris:
        return mesh
    import fast_simplification

    pts, fac = fast_simplification.simplify(
        mesh.vertices, mesh.faces, target_count=target_tris
    )
    out = trimesh.Trimesh(pts, fac, process=True)
    if len(out.faces) == 0:
        return mesh
    return out


def plane_for(axis_name, frac, bounds):
    axis = AXES[axis_name]
    lo, hi = float(bounds[0][axis]), float(bounds[1][axis])
    if not (0.02 <= frac <= 0.98):
        raise ValueError("La posición del plano debe estar entre 0.02 y 0.98")
    pos = lo + frac * (hi - lo)
    origin = np.zeros(3)
    origin[axis] = pos
    normal = np.zeros(3)
    normal[axis] = 1.0
    return origin, normal


def _validate_pieces(pieces, min_faces, original_volume):
    valid = []
    for p in pieces:
        if p is None or len(p.faces) < max(min_faces, 12):
            continue
        valid.append(p)
    if len(valid) < 2:
        raise ValueError("El plano no atraviesa el modelo: no genera dos piezas")
    for p in valid:
        if abs(p.volume) >= abs(original_volume) * 0.999:
            raise ValueError(
                "El plano pasa por aire: no divide el modelo en esa posición"
            )
    return valid


def cut_half(mesh, axis_name, frac):
    origin, normal = plane_for(axis_name, frac, mesh.bounds)
    low = trimesh.intersections.slice_mesh_plane(
        mesh, plane_normal=-normal, plane_origin=origin, cap=True
    )
    high = trimesh.intersections.slice_mesh_plane(
        mesh, plane_normal=normal, plane_origin=origin, cap=True
    )
    pieces = _validate_pieces(
        [low, high], int(MIN_FACE_RATIO * len(mesh.faces)), mesh.volume
    )
    splits = [{"a_index": 0, "b_index": 1, "origin": origin.tolist(), "normal": normal.tolist()}]
    return pieces, splits


def split_multi(mesh, parts):
    parts = int(parts)
    if parts < 2 or parts > 16:
        raise ValueError("Las partes deben estar entre 2 y 16")
    nodes = [mesh]
    splits = []

    while len(nodes) < parts:
        parent_idx = int(np.argmax([abs(n.volume) for n in nodes]))
        parent = nodes.pop(parent_idx)
        axis = int(np.argmax(parent.extents))
        mid = np.zeros(3)
        mid[axis] = (parent.bounds[0][axis] + parent.bounds[1][axis]) / 2.0
        normal = np.zeros(3)
        normal[axis] = 1.0
        a = trimesh.intersections.slice_mesh_plane(parent, -normal, mid, cap=True)
        b = trimesh.intersections.slice_mesh_plane(parent, normal, mid, cap=True)
        if len(a.faces) < 12 or len(b.faces) < 12:
            nodes.append(parent)
            break
        idx_a = len(nodes)
        idx_b = len(nodes) + 1
        nodes.extend([a, b])
        splits.append({
            "a_index": idx_a,
            "b_index": idx_b,
            "origin": mid.tolist(),
            "normal": normal.tolist(),
        })

    if len(nodes) < parts:
        pass
    return nodes[:parts], splits
