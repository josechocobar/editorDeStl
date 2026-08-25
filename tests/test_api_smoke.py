"""Smoke de la API: importar la app valida todas las rutas en tiempo de
definición (parámetros mal declarados en endpoints rompen el import)."""
from tests.helpers import get_client, sphere_bytes, upload_model


def test_app_imports_and_routes_register():
    from backend.main import app

    paths = {route.path for route in app.routes}
    assert "/api/models" in paths
    assert "/api/cut" in paths
    assert "/api/models/{model_id}/supports" in paths
    assert "/api/models/{model_id}/suggest-connector" in paths


def test_suggest_connector_query_params_accepted():
    client = get_client()
    resp = client.get("/api/models/inexistente/suggest-connector", params={"position": 0.4})
    assert resp.status_code == 404


# --- supports ---

def test_supports_endpoint_returns_downloadable_piece():
    client = get_client()
    info = upload_model(client)

    resp = client.post(f"/api/models/{info['id']}/supports", json={"angle": 50})
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
    client = get_client()
    resp = client.post("/api/models/abc123/supports", json={"angle": 500})
    assert resp.status_code == 422


def test_supports_accepts_minimum_contact_diameter_from_ui():
    client = get_client()
    info = upload_model(client)
    resp = client.post(
        f"/api/models/{info['id']}/supports", json={"contact_diameter": 0.2}
    )
    assert resp.status_code == 200, resp.text


def test_supports_endpoint_returns_informative_500(monkeypatch):
    from backend import main as m

    def boom(*args, **kwargs):
        raise RuntimeError("manifold explotó")

    monkeypatch.setattr(m.supports, "add_supports", boom)
    client = get_client()
    info = upload_model(client)
    resp = client.post(f"/api/models/{info['id']}/supports", json={})
    assert resp.status_code == 500
    assert "manifold explotó" in resp.json()["detail"]


def test_cut_multi_warns_on_parts_shortfall(monkeypatch):
    from backend import main as m

    def few_pieces(mesh, parts):
        return [mesh], []

    monkeypatch.setattr(m.mesh_ops, "split_multi", few_pieces)
    client = get_client()
    info = upload_model(client)
    resp = client.post(
        "/api/cut", json={"model_id": info["id"], "mode": "multi", "parts": 4}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["pieces"]) == 1
    assert any("1 de 4 partes" in w for w in data["warnings"])


# --- slug ids ---

def test_upload_returns_slug_id():
    client = get_client()
    info = upload_model(client, "mi_modelo_xyz")
    assert info["id"] == "mi_modelo_xyz"
    assert client.get(f"/api/models/{info['id']}").json()["name"] == "mi_modelo_xyz.stl"


def test_upload_slug_lowercased():
    client = get_client()
    up = client.post(
        "/api/models?replace=true",
        files={"file": ("CajaUpper.STL", sphere_bytes(), "model/stl")},
    )
    assert up.status_code == 200
    assert up.json()["id"] == "cajaupper"


# --- 409 / replace ---

def test_upload_duplicate_name_returns_409():
    client = get_client()
    info = upload_model(client, "duplicada")
    resp = client.post(
        "/api/models",
        files={"file": ("duplicada.stl", sphere_bytes(), "model/stl")},
    )
    assert resp.status_code == 409
    body = resp.json()
    assert "existing" in body
    assert body["existing"]["id"] == info["id"]


def test_upload_replace_overwrites():
    client = get_client()
    info = upload_model(client, "reemplazable")
    resp = client.post(
        "/api/models?replace=true",
        files={"file": ("reemplazable.stl", sphere_bytes(), "model/stl")},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == info["id"]


# --- list ---

def test_list_models_returns_uploaded():
    client = get_client()
    info = upload_model(client, "listable")
    listing = client.get("/api/models").json()
    ids = [m["id"] for m in listing]
    assert info["id"] in ids


# --- delete ---

def test_delete_model_removes_files():
    client = get_client()
    info = upload_model(client, "borrable")
    resp = client.delete(f"/api/models/{info['id']}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert client.get(f"/api/models/{info['id']}/preview").status_code == 404
    assert client.get(f"/api/models/{info['id']}").status_code == 404


# --- traversal ---

def test_upload_traversal_filename_sanitized():
    client = get_client()
    resp = client.post(
        "/api/models?replace=true",
        files={"file": ("../../secret_data.stl", sphere_bytes(), "model/stl")},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == "secret_data"


def test_delete_traversal_id_rejected():
    client = get_client()
    resp = client.delete("/api/models/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code in (400, 404, 405)
