# Soportes que bajaban del piso de impresión del modelo

**Fecha:** 2026-08-24
**Proyecto:** STLFiles
**Rama/commit del fix:** master (fix directo, ver git log)

## Síntoma

El e2e de la operación "solo soportes" sobre `samples/esfera.stl` mostraba
que el STL soportado llegaba a z = −15.0296 cuando el mínimo del modelo es
−15.0: había geometría de soportes **por debajo del piso de impresión**.
En corridas anteriores el exceso era 0.0 (−15.0 exacto): el defecto estaba
presente pero su magnitud dependía de dónde caían los contactos muestreados.

## Causa raíz

Tres defectos encadenados en `backend/supports.py`:

1. **Pad anclado al pie de columna más bajo** (`_base_pad` usaba
   `min(c.z for c in pad_feet)`). Las columnas que nacen de contactos bajos
   arrancan con la cabeza ya cerca del piso (`head_z = p.z − gap − cono`),
   así que ese mínimo podía quedar por debajo del min-z real y arrastraba
   TODO el disco base hacia abajo.
2. **Puntas cónicas sin tope inferior**: el cono de contacto cuelga
   `z_gap + TIP_CONE_LEN` (≈1.4 mm) debajo del punto de contacto. En un
   modelo convexo, un contacto a ~1 mm del piso produce una punta que se
   pasa del min-z (observado: 7.706 < 8.0).
3. Secundario: `pad_top = bed_z + 1.2` hardcodeado ignoraba
   `base_thickness` del spec (el parámetro de UI no afectaba dónde frenaban
   las columnas).

## Solución

- `_base_pad(pad_feet, thickness, margin=2.5, bed_z=None)`: ancla el disco
  al `bed_z` explícito (piso real de la pieza, pasado desde `add_supports`
  como `piece.bounds[0][2]`).
- `_tip_mesh(..., floor_z=None)` y `build_support_solids`: clamp coordinado
  a `bed_z` tanto del fondo del cono como de la cabeza de la columna (si
  solo se clampeará uno, quedaría un hueco o un solape desalineado).
- `build_support_solids(..., base_thickness=1.2)`: `pad_top` usa el espesor
  real; las columnas sin destino se hunden `max(thickness − SINK, thickness/2)`
  dentro del pad para garantizar fusión booleana aun con bases finas.

## Verificación

```bash
python3 -m pytest -q                       # 35 passed (2 regresiones nuevas)
python3 /tmp/op/e2e_check.py               # 16/16 OK contra docker
```

Regresiones en `tests/test_supports.py`:
`test_pad_sits_on_piece_floor_even_with_low_contacts` (min-z exacto con
contactos bajos) y `test_base_thickness_is_honored` (más espesor → más
volumen, resultado estanco).

## Lecciones

- Anclar geometría de apoyo a derivados indirectos (mínimo de pies de
  columna) en vez del dato primario (bounds del modelo) introduce bugs que
  solo aparecen según la distribución de muestras.
- Al acortar elementos de una cadena vertical (cono → columna → pad), el
  clamp debe aplicarse en TODOS los eslabones con el mismo valor o aparece
  hueco/solape.
- Un e2e con aserción geométrica exacta ("nada por debajo del min-z") valió
  más que diez asserts de watertightness: este bug pasaba todos los tests
  unitarios existentes.
