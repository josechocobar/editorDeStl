"""Helpers compartidos para tests de la API."""
import io
import uuid

import trimesh


def sphere_bytes(radius=12):
    sphere = trimesh.creation.icosphere(subdivisions=2, radius=radius)
    buf = io.BytesIO()
    sphere.export(buf, file_type="stl")
    return buf.getvalue()


def cube_bytes(size=20):
    cube = trimesh.creation.box(extents=[size, size, size])
    buf = io.BytesIO()
    cube.export(buf, file_type="stl")
    return buf.getvalue()


def upload_model(client, name=None, replace=True, stl_bytes=None):
    if name is None:
        name = f"model_{uuid.uuid4().hex[:6]}"
    fname = f"{name}.stl"
    data = stl_bytes or sphere_bytes()
    url = "/api/models" + ("?replace=true" if replace else "")
    up = client.post(url, files={"file": (fname, data, "model/stl")})
    assert up.status_code == 200, f"upload failed: {up.text}"
    return up.json()


def get_client():
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)
