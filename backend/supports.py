import math

import numpy as np
import trimesh

DOWN = np.array([0.0, 0.0, -1.0])
UP = np.array([0.0, 0.0, 1.0])

MIN_SURFACE_HEIGHT = 1.0
RAY_EPS = 0.05
SINK_MM = 0.4
MAX_CONTACTS = 600
MAX_BRANCH_RADIUS = 3.5
TIP_CONE_LEN = 1.2


class SupportError(ValueError):
    pass


def _sample_triangle(a, b, c, n):
    t1 = ((np.arange(n) + 0.5) * 0.618033988749895) % 1.0
    t2 = ((np.arange(n) + 0.5) * 0.754877666246693) % 1.0
    s = np.sqrt(t1)
    return (1 - s)[:, None] * a + (s * (1 - t2))[:, None] * b + (s * t2)[:, None] * c


def find_contact_points(mesh, angle_deg, spacing):
    """Puntos de contacto sobre voladizos según convención de slicers: un
    ángulo límite de X° soporta superficies cuya pendiente desde la vertical
    supera X (0° = todo, 90° = nada). Muestreo con separación mínima (R7/R8).
    Determinista: misma entrada → mismos puntos."""
    dot_min = math.sin(math.radians(angle_deg))
    mask = (mesh.face_normals @ DOWN) > dot_min
    if not mask.any():
        return []

    tris = mesh.triangles[mask]
    areas = mesh.area_faces[mask]
    bed_z = float(mesh.bounds[0][2])

    candidates = []
    cell_area = spacing * spacing
    for tri, area in zip(tris[np.argsort(-areas)], areas[np.argsort(-areas)]):
        n_pts = max(1, int(round(area / cell_area)))
        pts = _sample_triangle(tri[0], tri[1], tri[2], n_pts)
        keep = pts[:, 2] - bed_z > MIN_SURFACE_HEIGHT
        candidates.extend(pts[keep])

    if not candidates:
        return []
    if len(candidates) > MAX_CONTACTS:
        factor = math.sqrt(len(candidates) / MAX_CONTACTS)
        spacing *= factor
        cell_area = spacing * spacing

    chosen = []
    min_d2 = cell_area
    for p in candidates:
        d = np.array(chosen)[:, :2] - p[:2] if chosen else None
        if d is None or float(np.min(np.sum(d * d, axis=1))) >= min_d2:
            chosen.append(p)
            if len(chosen) >= MAX_CONTACTS:
                break
    return chosen


def _floor_below(mesh, xy, z_start):
    """Z del primer material del modelo debajo de (xy, z_start).
    None si el rayo llega a la cama sin tocar nada."""
    locs, _, _ = mesh.ray.intersects_location(
        ray_origins=[[float(xy[0]), float(xy[1]), float(z_start)]],
        ray_directions=[DOWN],
    )
    if len(locs) == 0:
        return None
    below = locs[locs[:, 2] < z_start - RAY_EPS]
    if len(below) == 0:
        return None
    return float(below[:, 2].max())


class _Column:
    __slots__ = ("xy", "z", "target_z", "r", "done")

    def __init__(self, xy, z, target_z, r):
        self.xy = np.asarray(xy, dtype=float)
        self.z = float(z)
        self.target_z = None if target_z is None else float(target_z)
        self.r = float(r)
        self.done = False


def _tapered_segment(p0, r0, p1, r1, sections=20):
    """Tronco de cono entre dos puntos con radios dados (rama del árbol)."""
    p0 = np.asarray(p0, dtype=float)
    p1 = np.asarray(p1, dtype=float)
    v = p1 - p0
    h = float(np.linalg.norm(v))
    if h < 1e-6:
        return None
    axis = v / h
    rot = trimesh.geometry.align_vectors(UP, axis)[:3, :3]

    theta = np.linspace(0.0, 2.0 * np.pi, sections, endpoint=False)
    ring = np.stack([np.cos(theta), np.sin(theta), np.zeros_like(theta)], axis=1)

    verts = np.vstack([
        p0 + ring @ (rot * r0).T,
        p0 + v + ring @ (rot * r1).T,
        [p0],
        [p0 + v],
    ])
    faces = []
    for i in range(sections):
        j = (i + 1) % sections
        faces.append([i, j, sections + j])
        faces.append([i, sections + j, sections + i])
        faces.append([2 * sections, j, i])
        faces.append([2 * sections + 1, sections + i, sections + j])
    m = trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=False)
    trimesh.repair.fix_normals(m)
    return m


def _tip_mesh(point, z_gap, contact_r, tip_r):
    """Punta cónica bajo el voladizo. El Z-gap queda como aire entre la
    superficie y el disco de contacto (regla R4)."""
    top_z = float(point[2]) - z_gap
    bot_z = top_z - TIP_CONE_LEN
    cone = _tapered_segment(
        [float(point[0]), float(point[1]), top_z], contact_r,
        [float(point[0]), float(point[1]), bot_z], tip_r,
    )
    return ([cone] if cone is not None else []), bot_z


def build_support_solids(mesh, contacts, tip_diameter, z_gap):
    """Columnas verticales que bajan nivel a nivel, se fusionan cuando están
    cerca y terminan sobre el modelo o en la base común (R1, R2 y R6)."""
    bed_z = float(mesh.bounds[0][2])
    pad_top = bed_z + 1.2
    tip_r = tip_diameter / 2.0
    dz = 4.0
    fuse_r = 2.5

    columns = []
    for p in contacts:
        head_z = float(p[2]) - z_gap - TIP_CONE_LEN
        floor_z = _floor_below(mesh, p[:2], head_z)
        target = None if floor_z is None else max(floor_z, pad_top)
        col = _Column(p[:2], head_z, target, tip_r)
        if target is not None and target >= col.z:
            col.done = True
        elif target is None and col.z <= pad_top:
            col.done = True
        columns.append(col)

    segments = []
    active = [c for c in columns if not c.done]
    while active:
        progressed = False
        for c in active:
            limit = c.target_z if c.target_z is not None else pad_top - SINK_MM
            nz = max(limit, c.z - dz)
            if nz < c.z - 1e-9:
                progressed = True
            seg = _tapered_segment([c.xy[0], c.xy[1], c.z], c.r,
                                   [c.xy[0], c.xy[1], nz], c.r)
            if seg is not None:
                segments.append(seg)
            c.z = nz
            if c.target_z is not None:
                if c.z <= c.target_z + 1e-9:
                    seg = _tapered_segment(
                        [c.xy[0], c.xy[1], c.z], c.r,
                        [c.xy[0], c.xy[1], c.target_z - SINK_MM], c.r)
                    if seg is not None:
                        segments.append(seg)
                    c.done = True
            elif c.z <= limit + 1e-9:
                c.done = True
        if not progressed:
            for c in active:
                if not c.done:
                    c.done = True
            break

        fused = []
        pool = [c for c in active if not c.done]
        used = [False] * len(pool)
        for i, ci in enumerate(pool):
            if used[i]:
                continue
            group = [ci]
            used[i] = True
            for j in range(i + 1, len(pool)):
                cj = pool[j]
                if not used[j] and all(
                    float(np.linalg.norm(cj.xy - g.xy)) < fuse_r for g in group
                ):
                    group.append(cj)
                    used[j] = True
            if len(group) == 1:
                fused.append(group[0])
                continue
            new_xy = np.mean([g.xy for g in group], axis=0)
            new_r = min(MAX_BRANCH_RADIUS,
                        math.sqrt(sum(g.r * g.r for g in group)))
            probe_z = min(g.z for g in group)
            floor_z = _floor_below(mesh, new_xy, probe_z)
            target = None if floor_z is None else max(floor_z, pad_top)
            nc = _Column(new_xy, probe_z, target, new_r)
            if target is not None and target >= nc.z:
                nc.done = True
            fused.append(nc)
        active = [c for c in fused if not c.done]

    pad_feet = [c for c in columns if c.target_z is None]
    return segments, pad_feet


def _base_pad(pad_feet, thickness, margin=2.5):
    """Disco base común donde terminan las columnas que llegan a la cama (R5)."""
    if not pad_feet:
        return None
    pts = np.array([c.xy for c in pad_feet])
    center = pts.mean(axis=0)
    radius = float(np.max(np.linalg.norm(pts - center, axis=1))) + margin
    pad = trimesh.creation.cylinder(radius=radius, height=thickness, sections=64)
    bed_z = float(min(c.z for c in pad_feet))
    pad.apply_translation([center[0], center[1], bed_z + thickness / 2.0])
    return pad


def add_supports(piece, spec):
    """Aplica soportes árbol a una pieza según el spec (dict) del request.

    Devuelve (pieza_soportada, info). Sin voladizos devuelve la pieza intacta
    con tips=0. Regla R10: verificar estanqueidad después de la unión."""
    contacts = find_contact_points(piece, spec["angle"], spec["spacing"])
    info = {"tips": len(contacts)}
    if not contacts:
        info["branches"] = 0
        info["added_volume_cm3"] = 0.0
        return piece, info

    solids = []
    tip_r = spec["tip_diameter"] / 2.0
    for p in contacts:
        parts, _ = _tip_mesh(p, spec["z_gap"], spec["contact_diameter"], tip_r)
        solids.extend(parts)

    segments, pad_feet = build_support_solids(
        piece, contacts, spec["tip_diameter"], spec["z_gap"])
    solids.extend(s for s in segments if s is not None)

    pad = _base_pad(pad_feet, spec["base_thickness"])
    if pad is not None:
        solids.append(pad)
    info["branches"] = len(solids)

    try:
        out = trimesh.boolean.union([piece] + solids, engine="manifold")
    except Exception as exc:
        raise SupportError(f"Fallo el booleano de soportes: {exc}") from exc
    if not out.is_watertight:
        raise SupportError("El resultado con soportes no es estanco")

    info["added_volume_cm3"] = round((abs(out.volume) - abs(piece.volume)) / 1000.0, 2)
    return out, info
