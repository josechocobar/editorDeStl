# Preview del plano de corte con dimensiones intercambiadas al elegir eje X

**Fecha:** 2026-08-23
**Proyecto:** stlfiles
**Rama/commit del fix:** feat/visor-decimado-sugerencia-zip (sin commit al momento del fix)

## Síntoma

En el visor, al elegir un eje de corte y luego cambiar a otro eje, el rectángulo
de preview del plano "no abraza" al modelo: queda con dimensiones que no
corresponden a la sección. Muy visible en figuras casi planas pero largas y
anchas (p. ej. 200×100×5 mm): cortando por X, el plano se dibuja sobresaliendo
100 mm en Z cuando el modelo mide 5 mm ahí.

## Causa raíz

`updatePlanePreview` en `web/app.js:166` elegía las dimensiones del
`PlaneGeometry` por orden arbitrario (`others[0]`, `others[1]`) sin considerar
cómo caen los ejes locales tras la rotación aplicada:

```js
// antes (incorrecto para eje X)
const others = axis === "x" ? ["y", "z"] : axis === "y" ? ["x", "z"] : ["x", "y"];
const w = box.max[others[0]] - box.min[others[0]];
const h = box.max[others[1]] - box.min[others[1]];
```

`PlaneGeometry(w, h)` extiende `w` por su eje local X y `h` por el local Y.
Con `rotation.y = π/2` (eje de corte X), la matriz Ry(90°) mapea local X → Z de
mundo y local Y → Y de mundo. Es decir, `w` se renderiza a lo largo de **Z** y
`h` a lo largo de **Y**, pero el código le asignaba `w = span(Y)` y
`h = span(Z)` → intercambio exacto de dimensiones. Para Y (`rotation.x = -π/2`,
local X → X, local Y → −Z) y Z (sin rotación) el orden resultó correcto de
casualidad.

## Solución

Dimensionar explícitamente por caso según qué eje de mundo recorre cada lado
del plano rotado:

```js
// después
let w, h;
if (axis === "x") {
  w = box.max.z - box.min.z;
  h = box.max.y - box.min.y;
} else if (axis === "y") {
  w = box.max.x - box.min.x;
  h = box.max.z - box.min.z;
} else {
  w = box.max.x - box.min.x;
  h = box.max.y - box.min.y;
}
```

## Verificación

Sin tests JS automatizados; verificación manual + sintaxis:

```bash
node --check web/app.js
```

Manual: cargar una figura plana-larga-ancha, alternar ejes X/Y/Z y mover el
slider → el rectángulo debe quedar siempre contenido dentro de la caja del
modelo (con margen 4%), sin importar el orden de selección de ejes.

## Lecciones

- Al orientar geometría con rotaciones, las dimensiones del primitivo deben
  asignarse según el eje de mundo donde va a caer cada eje LOCAL tras la
  rotación, no por conveniencia de orden.
- Regla mental: escribir primero el mapeo local→mundo de la rotación, después
  elegir w/h.
