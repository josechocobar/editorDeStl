"""Smoke de la API: importar la app valida todas las rutas en tiempo de
definición (parámetros mal declarados en endpoints rompen el import)."""


def test_app_imports_and_routes_register():
    from backend.main import app

    paths = {route.path for route in app.routes}
    assert "/api/models" in paths
    assert "/api/cut" in paths
    assert "/api/models/{model_id}/suggest-connector" in paths


def test_suggest_connector_query_params_accepted():
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    resp = client.get("/api/models/inexistente/suggest-connector", params={"position": 0.4})
    assert resp.status_code == 404
