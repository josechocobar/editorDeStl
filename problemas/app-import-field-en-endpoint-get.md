# App no arranca: Field de pydantic en firma de endpoint GET

**Fecha:** 2026-08-24
**Proyecto:** STLFiles
**Rama/commit del fix:** fix/app-import-query-param

## Síntoma

`docker compose up --build` terminaba en crash loop: uvicorn moría al
importar `backend/main.py` con

```
AssertionError: non-body parameters must be in path, query, header or cookie: position
```

El contenedor reiniciaba en loop y la API quedaba inaccesible (HTTP 000).

## Causa raíz

En el endpoint `GET /api/models/{model_id}/suggest-connector`
(backend/main.py:153) el parámetro query se declaró con `Field` de
**pydantic** en lugar de `Query` de **fastapi**:

```python
# antes
position: float = Field(default=0.5, ge=0.02, le=0.98),

# después
position: float = Query(default=0.5, ge=0.02, le=0.98),
```

FastAPI encuentra un `FieldInfo` crudo como default, no sabe clasificarlo,
termina tratándolo como parámetro de body y un GET no acepta body →
AssertionError en tiempo de definición de ruta.

Agravante de proceso: `pytest` nunca importaba `backend.main` (los tests
cubren solo mesh_ops/connectors/supports), así que un crash de import pasó
la suite completa en verde.

## Solución

1. `Query` de fastapi para el parámetro (único caso del error en el repo;
   los demás `Field` están dentro de modelos pydantic, donde sí van).
2. Test de regresión `tests/test_api_smoke.py`: importa la app (valida
   todas las rutas) y verifica que el endpoint acepte `position` por query.
3. Dockerfile/compose sin cambios: el bug era solo de código.

## Verificación

```bash
python3 -c "import backend.main"        # ya no explota
python3 -m pytest -q                    # 29 passed (2 nuevos)
docker compose up --build -d            # contenedor Up estable
curl -s "http://localhost:8321/api/models/x/suggest-connector?position=0.4"
```

## Lecciones

- En firmas de endpoints FastAPI: `Query/Header/Path/Cookie`; `Field` es
  SOLO para modelos pydantic. Los dos tienen API parecida (`default`, `ge`,
  `le`) y ese parecido es la trampa.
- Si un módulo no lo toca ningún test, su import puede estar roto sin que
  la suite se entere: un smoke test de import cuesta 3 líneas y detecta
  toda rotura de rutas en tiempo de definición.
