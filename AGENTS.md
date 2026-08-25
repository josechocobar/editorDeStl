# AGENTS.md — Mapa del proyecto STLFiles

Guía de alto nivel para sesiones de IA. Leé esto primero; abrí código solo
cuando necesites detalle de implementación.

## Qué es

Splitter de modelos STL estilo MeshMixer para imprimir en piezas (FDM/resina),
con conectores de encastre y generación de soportes para minis.
Backend Python + frontend vanilla sin build step.

## Estructura

```
backend/
  main.py           FastAPI. Endpoints REST + montaje estático de web/.
                    Modelos pydantic: CutRequest(CutParams),
                    SupportsSpec(SupportsParams).
  operations/       Patrón operation (lógica de negocio separada de HTTP):
    __init__.py     OperationResult dataclass (pieces, names, operation, ...).
    cut.py          CutParams + run(): corte + conectores + soportes.
    supports.py     SupportsParams + run(): soportes sobre modelo entero.
  mesh_ops.py       Carga/corte de mallas: load_mesh, model_info,
                    decimate_for_preview, cut_half, split_multi.
  connectors.py     Encastes: suggest, compute_sites, apply_connector.
  supports.py       Soportes árbol: find_contact_points, build_support_solids,
                    add_supports (reglas R1–R10).
web/
  index.html        Panel: 1·Modelo (dropzone) 2·Operación (Cortar en piezas |
                    Solo soportes) 3·Piezas|Resultado (resultados + zip).
                    Viewport + HUD + loading overlay.
  js/
    app.js          Entry: estado global, wiring UI, persistencia sesión,
                    adoptModel, librería de archivos (CRUD).
    api.js          Transporte HTTP: uploadModel, cutModel, generateSupports,
                    listModels, deleteModel, suggestConnector.
    scene.js        Three.js sin DOM: initScene, fitCamera,
                    updatePlanePreview (dimensiones por eje).
    operations.js  Registry de operaciones: OPERATIONS[op] con
                    collectParams + execute. Para agregar una operación.
  vendor/           three.module.js vendoreado (offline).
tests/
  helpers.py        Shared: sphere_bytes, cube_bytes, upload_model, get_client.
  test_mesh_ops.py  Corte/conectores/suggest.
  test_supports.py  Soportes.
  test_api_smoke.py Rutas + e2e (46 tests).
samples/          STLs de prueba (caja_con_agujero, esfera, letra_L).
data/             Runtime: models/ (STL+meta json), jobs/ (piezas por job).
docs/             investigacion-soportes.md (tipos + reglas vinculantes R1-R10)
problemas/        Bug log: 1 md por bug resuelto (kebab-case, español).
BITACORA.md       Historial de construcción, errores y lecciones (E1, E2...).
```

## API

```
POST /api/models                      upload STL → id + medidas (slug por nombre)
                                     409 si nombre existe (resp con existing)
GET  /api/models                      lista todos los modelos (meta, mtime desc)
GET  /api/models/{id}/preview         STL decimado (cache .preview.stl)
GET  /api/models/{id}/suggest-connector   sugerencia pin según cara de corte
POST /api/models/{id}/supports        soportes al modelo entero → job 1 pieza
DELETE /api/models/{id}               borra stl + meta + preview
POST /api/cut                         corte → job {pieces, splits, warnings}
GET  /api/jobs/{job}/pieces/{i}       STL pieza (+ /preview decimado)
GET  /api/jobs/{job}/zip              zip piezas + {corte|soportes}_info.json
```

## Convenciones (no negociables)

- Booleanos SIEMPRE `engine="manifold"`; verificar `is_watertight` después
  de cada operación que modifica malla.
- Errores y docstrings en español; errores de dominio heredan ValueError
  (`ConnectorError`, `SupportError`) y llegan al usuario como warning, no
  rompen el job entero.
- Commits convencionales en inglés, sin atribución de IA.
- Bug resuelto → entrada en `problemas/` ANTES de commitear (skill problema-log).
- Frontend sin framework ni build: importmap + vendor offline.
- Determinismo: nada de RNG sin seed en geometría (mismo input → mismo output).

## Adding an operation

1. **Backend**: crear `backend/operations/nueva_op.py` con `Params(NamedTuple)` + `run(mesh, params) -> OperationResult`.
2. **Endpoint**: agregar modelo pydantic en `main.py` (`NuevaOpRequest(NuevaOpParams)`), endpoint que llama `run()`, retorna `OperationResult`.
3. **Frontend**: agregar entrada en `web/js/operations.js` → `OPERATIONS["nueva_op"] = { label, collectParams, execute }`.
4. **UI**: controles HTML en `index.html` (radio pill + fieldset); el botón "Cortar modelo" usa el registry genérico.
5. **Tests**: test en `tests/test_api_smoke.py` + test de dominio si hay lógica no trivial.
6. **Commit**: convencional, sin atribución IA.

## Comandos

```bash
pytest -q                            # tests desde la raíz
uvicorn backend.main:app --reload    # dev server
docker compose up --build            # deploy
for f in web/js/*.js; do node --check "${f%.js}.mjs" 2>/dev/null || node --check --input-type=module < "$f"; done  # sintaxis frontend (copiar como .mjs: node trata .js como CommonJS)
```

## Gotchas conocidos

- El preview del plano de corte dibuja dimensiones según mapeo local→mundo de
  cada rotación de eje (bug histórico: ver problemas/preview-plano-*.md).
- `clearGroup` tolera meshes null (primer load).
- Previews se cachean como `<nombre>.preview.stl`; invalidación por mtime.
- Agujero de conector = diámetro + 2×holgura (compensación FDM).
