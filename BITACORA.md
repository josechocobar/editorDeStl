# Bitácora — STLFiles

Registro completo de la construcción del proyecto: qué se hizo, qué falló,
cómo se reparó y con qué tests se verificó.

---

## 1. Qué se construyó

Splitter de modelos STL estilo MeshMixer en la web:

| Capa | Tecnología | Archivos |
|------|-----------|----------|
| Corte y booleanos | trimesh 5.0 + manifold3d | `backend/mesh_ops.py`, `backend/connectors.py` |
| API REST | FastAPI + uvicorn | `backend/main.py` |
| Frontend | HTML/CSS/JS puro + Three.js 0.170 vendoreado (offline) | `web/` |
| Deploy | Docker + docker-compose | `Dockerfile`, `docker-compose.yml` |
| Tests | pytest | `tests/test_mesh_ops.py` |

### Decisiones de diseño

- **`slice_mesh_plane(cap=True)`**: el corte por plano tapa la sección nueva con
  triángulos → las piezas siempre salen watertight (imprimibles).
- **Motor de booleanos `manifold`**: verificado empíricamente antes de escribir
  código de producción (union/difference estancas en todos los casos de prueba).
- **Multi-parte recursiva (kd-tree)**: cada pieza se divide por su eje más largo;
  se registra qué par de piezas nace de cada corte para colocar conectores solo
  entre piezas hermanas.
- **Conectores asimétricos para FDM**: agujero = `diámetro + 2 × holgura`,
  pin nominal. La holgura default (0.25 mm) compensa la expansión del material.
- **Frontend sin build**: HTML/CSS/JS vanilla con importmap; Three.js bajado a
  `web/vendor/` para funcionar sin internet.

### Flujo de la API

```
POST /api/models            upload STL → id + medidas/volumen/triángulos
POST /api/cut               corte → job con piezas, splits, conectores, warnings
GET  /api/jobs/{job}/pieces/{i}   STL de una pieza
GET  /api/jobs/{job}/zip    ZIP con todas las piezas + corte_info.json
```

---

## 2. Errores cometidos y cómo se repararon

### E1 · Corte sin tapa → mallas abiertas

- **Síntoma**: primer script de verificación dio `is_watertight: False` y
  `trimesh.boolean.union` reventó con `ValueError: Not all meshes are volumes!`.
- **Causa**: usé el corte por plano sin generar la tapa; las mitades quedaban
  como cascarones abiertos y manifold rechaza sólidos inválidos.
- **Arreglo**: `trimesh.intersections.slice_mesh_plane(..., cap=True)` antes de
  cualquier booleano. Verificado con roundtrip de export/import STL.
- **Lección**: verificar la API con un script mínimo ANTES de escribir módulos.

### E2 · Test con premisa equivocada (3 iteraciones)

El caso "el plano pasa por aire debe dar error" me llevó tres intentos:

1. **Intento 1**: cortar una caja en `frac=0.98`. No lanza error porque esa
   posición SIGUE dentro de la caja (el clamp es sobre el bounding box). El test
   además tenía una línea basura (`if False else None`). Mal escrito y mal pensado.
2. **Intento 2**: dos toros apilados, cortando en el hueco entre ambos. **No era
   un error real**: `slice_mesh_plane` separa geometría desconectada aunque el
   plano no toque material — devuelve los dos toros como piezas legítimas.
3. **Intento 3**: forma de C restada de un cilindro. La resta cambió el bounding
   box y mi fracción cayó dentro de material. De nuevo, premisa sin verificar.
4. **Final correcto**: esfera grande + satélite diminuto, corte entre ambos → una
   pieza se queda con ≥99.9 % del volumen. Eso SÍ es un corte al vacío útil.
   Se agregó la regla de validación por volumen en `_validate_pieces`.
- **Lección**: el comportamiento esperado hay que diseñarlo contra la semántica
  real de la librería, no contra la intuición. Cada intento se verificó con un
  script suelto antes de tocar el test.

### E3 · Piezas invertidas en el test de conectores

- **Síntoma**: `assert abs(hole_cut.volume) < abs(low.volume)` fallaba con
  volúmenes EXACTAMENTE iguales (16000.0 == 16000.0).
- **Causa**: pasé `(high, low)` invertidos a `apply_connector`. Los pines deben
  ir en la pieza inferior sobresaliendo hacia arriba; yo los uní a la superior
  (sobresalían al vacío) y los agujeros quedaban flotando fuera de la inferior.
  Manifold hace `difference` con un cortador que no intersecta y devuelve el
  original sin avisar → volumen idéntico.
- **Arreglo**: orden correcto `(low, high)` + el test ahora también valida
  `dist >= diámetro` entre sitios.
- **Lección**: un booleano con resultado "sin cambios" es silencioso; los tests
  de volumen son la única red.

### E4 · `pkill -f` suicida

- **Síntoma**: el comando `pkill -f "uvicorn backend.main"` colgó hasta timeout.
- **Causa**: `-f` matchea la línea completa de comandos — incluida la del propio
  shell que ejecutaba el pkill. Me maté a mí mismo. Además el heredoc posterior
  nunca se escribió.
- **Arreglo**: matar por PID obtenido de `ss -tlnp`, y archivos vía herramienta
  de escritura, no heredocs encadenados tras comandos que pueden morir.

### E5 · Proceso de fondo inestable (motivó Docker)

- **Síntoma**: el usuario no podía ver la app; uvicorn arrancaba y aparecía
  muerto después; algunos relanzamientos recibían shutdown inmediato.
- **Causa raíz doble**: (1) uvicorn escuchaba solo en `127.0.0.1`; (2) procesos
  de fondo atados a la sesión del shell mueren con la sesión.
- **Arreglo**: Dockerfile + compose siguiendo las convenciones de `printmaster`
  (`python:3.12-slim`, `--host 0.0.0.0`, puerto 8321, volumen `./data:/app/data`,
  `restart: unless-stopped`). Logs centralizados con `docker compose logs`.

### E6 · Bug latente: faltaba `rtree` (destapado por Docker)

- **Síntoma**: en el contenedor, cortar `caja_con_agujero.stl` en 4 partes dio
  `500 Internal Server Error`. Traceback en logs de Docker:
  `ModuleNotFoundError: No module named 'rtree'` desde
  `trimesh/path/polygons.py::enclosure_tree`.
- **Causa**: la tapa de secciones anulares (cara de corte con agujero) requiere
  `rtree`. Nunca lo habíamos necesitado: todos los tests previos usaban sólidos
  sin huecos. El bug existía también en el host — simplemente nadie había cortado
  un modelo con agujero en modo multi.
- **Arreglo**: `rtree` en `requirements.txt` (wheel manylinux con libspatialindex
  embebido), instalado en host, test de regresión dedicado.
- **Bonus**: el endpoint devolvía HTML crudo en errores no controlados; ahora
  `Exception` genérica → JSON 500 con mensaje + log completo. Y
  `trimesh.load` → `load_mesh` para eliminar el WARNING de compatibilidad.

### E7 · Conectores superpuestos y margen irrealista

- **Síntoma**: en caras chicas, sitios generados a 3 mm entre sí para pines de
  6 mm — se fusionarían al imprimir.
- **Causa doble**: el layout repartía puntos con `linspace` sin validar
  separación mínima; y el margen de borde (`1.35 × diámetro` por lado) era tan
  conservador que descartaba caras válidas (un pin necesita pared ≈ radio + 1.5 mm,
  no 1.35 diámetros).
- **Arreglo** (`connectors.py`):
  - margen = `diámetro/2 + 1.5 mm` por lado;
  - `_row_positions()` valida `k·d + (k-1)·0.6d ≤ span` antes de ubicar;
  - estrategia fila → columna → grilla √n × √n, todas validadas;
  - umbral de vértices de cara 8 → 4 (una tapa legítima de 7 vértices era rechazada);
  - mensaje de error honesto con dimensiones: `"No entran 2 conectores de 5.0 mm
    en la cara útil de 4.0 x 12.0 mm"`.

### E8 · Carrera curl-vs-arranque del contenedor

- **Síntoma**: `curl` inmediato tras `compose up --build` devolvía vacío/000.
- **Causa**: uvicorn todavía no terminaba de bindear cuando el request salía.
- **Arreglo**: bucle de espera hasta `HTTP 200` antes de testear (patrón de
  healthcheck manual).

### E9 · Menores

- `pip` no existía en PATH → `python3 -m pip` (y flag `--break-system-packages`
  en el Python de linuxbrew).
- `pymeshlab` escupe warnings de plugins Qt bajo este intérprete; quedó instalado
  pero NO está en requirements: el pipeline usa trimesh+manifold únicamente.

---

## 3. Tests corridos

Suite: `python3 -m pytest tests/ -q` → **12 passed** (host y reconstruida en imagen).

| # | Test | Qué valida | Cubre el bug |
|---|------|-----------|--------------|
| 1 | `test_cut_half_box_two_watertight_pieces` | 2 piezas estancas, volumen conservado | E1 |
| 2 | `test_cut_half_position_controls_ratio` | posición 0.75 ⇒ ~75 % del volumen en una pieza | — |
| 3 | `test_cut_half_invalid_position_raises` | fracción fuera de [0.02, 0.98] ⇒ ValueError | E2.1 |
| 4 | `test_cut_half_plane_through_air_raises` | pieza con ≥99.9 % del volumen ⇒ ValueError | E2.4 |
| 5 | `test_split_multi_sphere_four_parts` | 4 piezas estancas, 3 splits, volumen conservado | — |
| 6 | `test_split_multi_annular_section_box_with_hole` | modelo con agujero atraviesa todo el pipeline | E6 |
| 7 | `test_pin_connector_watertight_and_fits` | pin crece/agujero mengua volumen, sitios a ≥ diámetro, largo de pin correcto | E3, E7 |
| 8 | `test_sites_reject_when_count_does_not_fit` | 8 pines de 12 mm en cara chica ⇒ ConnectorError | E7 |
| 9 | `test_connector_sites_inset_from_edges` | sitios dentro del margen de borde | E7 |
| 10 | `test_prism_connector_works` | espiga cuadrada watertight en ambas piezas | — |
| 11 | `test_connector_on_tiny_face_raises` | cara de 6 mm con pin de 6 mm ⇒ ConnectorError | E7 |
| 12 | `test_load_and_info_roundtrip` | export→import STL, info consistente (dims ±0.5 mm) | E1 |

### Verificación manual end-to-end (curl contra el contenedor)

```
POST /api/models  samples/esfera.stl           → 200, dims [30,30,30], watertight
POST /api/models  samples/caja_con_agujero.stl → 200, watertight
POST /api/cut     multi=4 + pin d6             → 4 piezas watertight, ZIP ok
GET  /api/jobs/{id}/zip                        → 5 archivos (4 STL + corte_info.json)
GET  /                                         → 200 (frontend)
GET  /app.js                                   → 200
POST /api/cut     parts=99                     → 422 con detalle de validación pydantic
```

Casos de regresión final post-fix E7:

- `caja_con_agujero` multi=4 + 1×pin d4 → **3/3 cortes con conector, 0 avisos**
- `esfera` multi=4 + 2×pin d6 → **3/3 cortes con conector, 0 avisos**

---

## 4. Commits

| Commit | Contenido |
|--------|-----------|
| `3e503e1` | feat: splitter web completo (backend, frontend, tests, samples) |
| `a2a0f90` | fix: docker deploy, rtree para tapas anulares, layout anti-colisión de conectores |

---

## Lecciones para el próximo ciclo

1. **Probar con geometría hostil temprano**: el bug de `rtree` existió desde el
   día 1; solo apareció con un modelo con agujero. Los fixtures de test deben
   incluir secciones anulares, cóncavas y desconectadas.
2. **Los booleanos silenciosos mienten**: siempre asertar por volumen, nunca
   confiar en que "no explotó" = "salió bien".
3. **Validar premisas de test con scripts sueltos** antes de escribirlos: tres
   iteraciones por no hacerlo.
4. **Docker primero** para servicios locales: resuelve binding de red, ciclo de
   vida del proceso y logs en un solo movimiento.
