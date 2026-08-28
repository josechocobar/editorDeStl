# STLFiles

Splitter de modelos 3D estilo MeshMixer en la web: subís un `.stl`, lo cortás en piezas
con un plano (o en N partes), les agregás conectores de encastre (pin cilíndrico o
espiga prismática) y/o soportes árbol para minis, y te bajás los STL listos para imprimir.

## Capturas

![Vista del editor 1](./proyecto-1.png)

![Vista del editor 2](./proyecto2.png)

## Stack

- **Backend**: FastAPI + [trimesh](https://trimesh.org) con motor de booleanos [manifold3d](https://github.com/elalish/manifold)
- **Frontend**: HTML/CSS/JS puro + Three.js (vendoreado, funciona offline)

## Levantar con Docker

```bash
docker compose up --build
```

Abrir http://localhost:8321 — los datos quedan en `./data` (montado como volumen).

### Configuración (opcional)

```bash
cp .env.example .env   # después editás .env a gusto
```

| Variable | Default | Qué hace |
|----------|---------|----------|
| `STLFILES_PORT` | `8321` | Puerto del host donde se publica la app |
| `STLFILES_DATA` | `./data` | Dónde se guardan uploads y jobs |

## Levantar en local (dev)

```bash
python3 -m pip install -r requirements.txt
python3 -m uvicorn backend.main:app --reload --port 8321
```

## Uso

1. **Modelo**: arrastrás el `.stl`.
2. **Operación**:
   - *Cortar en piezas*: plano (eje + posición, con preview en vivo) o N partes;
     conectores de encastre opcionales; soportes opcionales por pieza.
   - *Solo soportes*: genera soportes árbol sobre el modelo entero.
3. **Resultado**: STL de cada pieza para descargar individualmente o todo junto en un ZIP.

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

### Soportes para minis

Soportes estilo árbol (reglas R1–R10 en `docs/investigacion-soportes.md`): puntas
cónicas con z-gap sobre los voladizos, columnas que bajan y se fusionan, y una base
común donde llega la cama. Parámetros: ángulo de voladizo, diámetros de punta/contacto,
separación, z-gap y espesor de base.

Si un voladizo tiene material debajo (propio de la pieza), la columna descansa sobre
él en vez de bajar hasta la base.

## API

| Endpoint | Descripción |
|----------|-------------|
| `POST /api/models` | Upload STL (multipart) → info: medidas, volumen, triángulos |
| `GET /api/models/{id}/file` | STL original |
| `GET /api/models/{id}/preview` | STL decimado para el visor (cacheado) |
| `GET /api/models/{id}/suggest-connector` | Sugerencia de pin según la cara de corte |
| `POST /api/models/{id}/supports` | Soportes sobre el modelo entero → job de 1 pieza |
| `POST /api/cut` | Corte (+ conectores/soportes opcionales) → job con piezas, splits y warnings |
| `GET /api/jobs/{job}/pieces/{i}` | STL de una pieza |
| `GET /api/jobs/{job}/pieces/{i}/preview` | Preview decimado de una pieza |
| `GET /api/jobs/{job}/zip` | ZIP con las piezas + `{corte\|soportes}_info.json` |

## Tests

```bash
python3 -m pytest tests/ -q
```

## Estructura

```
backend/
  main.py        FastAPI: upload, corte, soportes, descargas, static
  mesh_ops.py    carga, info, corte por plano, split recursivo, previews
  connectors.py  sitios de encastre + primitivas pin/prisma + booleanos
  supports.py    detección de voladizos + árbol de soportes + base común
web/             index.html, style.css, js/ (ES modules), vendor/ (three.js local)
tests/           pytest del motor de corte, conectores, soportes y API
samples/         STLs de ejemplo para probar
docs/            investigación y reglas de soportes
problemas/       bug log: un md por bug resuelto
data/            uploads y jobs (gitignoreado)
```

Más detalle técnico para contribuir: [`AGENTS.md`](AGENTS.md).
