# Conectores flotando fuera de la cara de corte

**Fecha:** 2026-08-23
**Proyecto:** stlfiles
**Rama/commit del fix:** fix/conector-fuera-de-cara

## Síntoma

Los conectores (pins/prismas) se colocaban en posiciones donde no había material:
flotaban al costado del modelo o tapaban agujeros. En la letra L cortada por la
mitad, el algoritmo viejo proponía sitios sobre la zona cóncava vacía.

## Causa raíz

`compute_sites()` solo miraba UNA pieza y derivaba los límites de candidatos del
bounding box de esa pieza. Un bbox es un rectángulo: incluye zonas sin material
(vacíos, agujeros, zonas cóncavas). Colocar un pin requiere material en AMBAS
caras enfrentadas (el pin se une a la pieza macho y el agujero se resta de la
hembra); validar contra una sola pieza era insuficiente por diseño.

## Solución

`backend/connectors.py`: nueva firma y validación por ray-cast.

- Firma: `compute_sites(piece_male, piece_female, origin, normal, count, diameter, depth=8.0)`.
- `_contains(mesh, point)`: `mesh.contains([point])` (ray casting de trimesh).
- Cada candidato se valida con dos sondas:
  - `base - n*0.8` dentro de `piece_male` (material para el pin).
  - `base + n*(depth*0.5)` dentro de `piece_female` (material para el agujero).
- Los límites de candidatos salen de vértices CERCANOS AL PLANO (`dist < eps`,
  eps = 2% del span), no del bbox completo.
- Si no hay suficientes válidos, devuelve menos sitios en vez de fallar;
  `main.py` emite warning honesto ("se ubicaron X de Y").

```python
# antes (una pieza + bbox completo)
sites = compute_sites(piece, origin, normal, count, diameter)

# después (ambas piezas + sondas de contenido)
sites = compute_sites(piece_male, piece_female, origin, normal,
                      count, diameter, depth)
```

## Verificación

```bash
python3 -m pytest tests/ -q   # 15 passed
# End-to-end: letra L → 1 sitio válido [0, -22.2, 2.8] (sobre la base, x=0)
# caja_con_agujero → 4 sitios alrededor del agujero central, ninguno encima
```

## Lecciones

- El bounding box MIENTRE sobre geometría cóncava: nunca derives posiciones de
  superficie desde el bbox; usa vértices cercanos al plano.
- Validar "hay material" = ray casting en TODAS las piezas involucradas, no una.
- Mejor devolver menos elementos con warning que fallar todo el request.
