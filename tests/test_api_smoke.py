"""Smoke de la API: importar la app valida todas las rutas en tiempo de
definición (parámetros mal declarados en endpoints rompen el import)."""
import io

import trimesh


def test_app_imports_and_routes_register():
    from backend.main import app

    paths = {route.path for route in app.routes}
    assert "/api/models" in paths
    assert "/api/cut" in paths
    assert "/api/models/{model_id}/supports" in paths
    assert "/api/models/{model_id}/suggest-connector" in paths


def test_suggest_connector_query_params_accepted():
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    resp = client.get("/api/models/inexistente/suggest-connector", params={"position": 0.4})
    assert resp.status_code == 404


def _sphere_bytes():
    sphere = trimesh.creation.icosphere(subdivisions=2, radius=12)
    buf = io.BytesIO()
    sphere.export(buf, file_type="stl")
    return buf.getvalue()


def test_supports_endpoint_returns_downloadable_piece():
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    up = client.post(
        "/api/models",
        files={"file": ("esfera_test.stl", _sphere_bytes(), "model/stl")},
    )
    assert up.status_code == 200, up.text
    model_id = up.json()["id"]

    resp = client.post(f"/api/models/{model_id}/supports", json={"angle": 50})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["operation"] == "soportes"
    assert len(data["pieces"]) == 1
    assert data["pieces"][0]["watertight"]
    assert data["pieces"][0]["name"].endswith("_con_soportes.stl")
    assert data["supports"][0]["tips"] > 0
    assert not data["warnings"]

    stl = client.get(data["pieces"][0]["file_url"])
    assert stl.status_code == 200
    assert len(stl.content) > 0

    zipped = client.get(f"/api/jobs/{data['job_id']}/zip")
    assert zipped.status_code == 200
    assert zipped.headers["content-type"].startswith("application/zip")


def test_supports_endpoint_validates_params():
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    resp = client.post("/api/models/abc123/supports", json={"angle": 500})
    assert resp.status_code == 422


def test_supports_accepts_minimum_contact_diameter_from_ui():
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    up = client.post(
        "/api/models",
        files={"file": ("esfera_test.stl", _sphere_bytes(), "model/stl")},
    )
    model_id = up.json()["id"]
    resp = client.post(
        f"/api/models/{model_id}/supports", json={"contact_diameter": 0.2}
    )
    assert resp.status_code == 200, resp.text
