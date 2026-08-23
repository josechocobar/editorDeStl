# STLFiles

Splitter de modelos 3D estilo MeshMixer en la web: subís un `.stl`, lo cortás en piezas
con un plano (o en N partes), les agregás conectores de encastre (pin cilíndrico o
espiga prismática) y te bajás los STL listos para imprimir.

## Stack

- **Backend**: FastAPI + [trimesh](https://trimesh.org) con motor de booleanos [manifold3d](https://github.com/elalish/manifold)
- **Frontend**: HTML/CSS/JS puro + Three.js (vendoreado, funciona offline)

## Uso

```bash
python3 -m pip install -r requirements.txt
python3 -m uvicorn backend.main:app --reload --port 8321
```

Abrir http://localhost:8321

## Cómo funciona el corte

| Modo | Qué hace |
|------|----------|
| **Mitad (plano)** | Elegís eje X/Y/Z y posición del plano; lo ves en vivo como plano rojo translúcido. Corta en 2 con tapa (`cap=True`), siempre watertight. |
| **Varias partes** | Elegís 2–16 partes; se divide recursivamente cada pieza por su eje más largo (kd-tree), registrando qué par de piezas nace de cada corte. |

### Conectores

Cada corte genera sitios de encastre sobre la cara de corte (grilla dentro del área
útil, con margen de seguridad):

- **Pin**: cilindro que sobresale de una pieza + agujero en la otra.
- **Prisma**: espiga cuadrada + cavidad cuadrada.

Parámetros: diámetro/lado, profundidad de enchufe, holgura (el agujero se agranda
`2 × holgura`, default `0.25 mm` pensado para FDM) y cantidad por corte.

Si un conector falla (cara muy chica, booleano raro), la API lo omite y lo reporta en
`warnings` — las piezas salen iguales, sin encastre en ese corte.

## API

| Endpoint | Descripción |
|----------|-------------|
| `POST /api/models` | Upload STL (multipart) → info: medidas, volumen, triángulos |
| `GET /api/models/{id}/file` | STL original |
| `POST /api/cut` | Corte → job con piezas, splits y warnings |
| `GET /api/jobs/{job}/pieces/{i}` | STL de una pieza |
| `GET /api/jobs/{job}/zip` | ZIP con todas las piezas + `corte_info.json` |

## Tests

```bash
python3 -m pytest tests/ -q
```

## Estructura

```
backend/
  main.py        FastAPI: upload, corte, descargas, static
  mesh_ops.py    carga, info, corte por plano, split recursivo
  connectors.py  sitios de encastre + primitivas pin/prisma + booleanos
web/             index.html, style.css, app.js, vendor/ (three.js local)
tests/           pytest del motor de corte y conectores
samples/         STLs de ejemplo para probar
data/            uploads y jobs (gitignoreado)
```
