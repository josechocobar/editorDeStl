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
  main.py         FastAPI. Endpoints REST + montaje estático de web/.
                  Modelos pydantic: ConnectorSpec, SupportsSpec, CutRequest.
  mesh_ops.py     Carga/corte de mallas: load_mesh, model_info,
                  decimate_for_preview (previews livianos), plane_for,
                  cut_half (slice + cap), split_multi (recursivo kd).
  connectors.py   Encastes entre piezas hermanas: suggest (reglas FDM),
                  compute_sites (valida material en ambas caras),
                  apply_connector (pin/prism + agujero con holgura).
  supports.py     Soportes árbol para minis (reglas R1–R10 en
                  docs/investigacion-soportes.md): find_contact_points
                  (voladizos por normales), build_support_solids (columnas
                  que bajan, se fusionan, base común), add_supports (union).
web/
  index.html      Panel: 1·Modelo (dropzone) 2·Corte (eje/pos/conectores/
                  soportes) 3·Piezas (resultados + zip). Viewport + HUD.
  app.js          Three.js: escena `world` rotada -90° en X (Z-up modelo vs
                  Y-up escena), updatePlanePreview (dimensiones por eje, ver
                  problemas/), upload/cut flows, explode slider, sugerencia
                  de conectores (fetchSuggestion con debounce 300ms).
  vendor/         three.module.js vendoreado (offline).
tests/            pytest. test_mesh_ops.py (corte/conectores/suggest),
                  test_supports.py (soportes).
samples/          STLs de prueba (caja_con_agujero, esfera, letra_L).
data/             Runtime: models/ (STL+meta json), jobs/ (piezas por job).
docs/             investigacion-soportes.md (tipos + reglas vinculantes R1-R10)
problemas/        Bug log: 1 md por bug resuelto (kebab-case, español).
BITACORA.md       Historial de construcción, errores y lecciones (E1, E2...).
```

## API

```
POST /api/models                      upload STL → id + medidas
GET  /api/models/{id}/preview         STL decimado (cache .preview.stl)
GET  /api/models/{id}/suggest-connector   sugerencia pin según cara de corte
POST /api/cut                         corte → job {pieces, splits, warnings}
GET  /api/jobs/{job}/pieces/{i}       STL pieza (+ /preview decimado)
GET  /api/jobs/{job}/zip              zip piezas + corte_info.json
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

## Comandos

```bash
pytest -q                            # tests desde la raíz
uvicorn backend.main:app --reload    # dev server
docker compose up --build            # deploy
node --check web/app.js              # sintaxis frontend (no hay linter JS)
```

## Gotchas conocidos

- El preview del plano de corte dibuja dimensiones según mapeo local→mundo de
  cada rotación de eje (bug histórico: ver problemas/preview-plano-*.md).
- `clearGroup` tolera meshes null (primer load).
- Previews se cachean como `<nombre>.preview.stl`; invalidación por mtime.
- Agujero de conector = diámetro + 2×holgura (compensación FDM).
