# TypeError al cargar el primer STL: clearGroup sobre null

**Fecha:** 2026-08-23
**Proyecto:** stlfiles
**Rama/commit del fix:** fix/stl-null-cleargroup

## Síntoma

```
TypeError: Cannot read properties of null (reading 'geometry')
    at clearGroup (app.js:93:7)
    at app.js:123:5
    at Object.onLoad (STLLoader.js:86:5)
```

El modelo no se mostraba en el visor. El usuario sospechó del tamaño (>40 MB).

## Causa raíz

`loadOriginal()` llamaba `clearGroup([state.originalMesh, ...state.pieceMeshes])`
antes de crear el mesh. En la PRIMERA carga `state.originalMesh` es `null`
(valor inicial), y `clearGroup` hacía `m.geometry.dispose()` sin verificar.
Crash determinista e independiente del tamaño: la prueba es que el error salta
DENTRO del callback `onLoad`, o sea que STLLoader YA parseó el STL completo con
éxito — si fuera problema de tamaño, fallaría antes (en parse o en memoria).

## Solución

Guardia en `clearGroup` (web/app.js):

```js
for (const m of list) {
  if (!m) continue;   // ← nuevo
  world.remove(m);
  m.geometry.dispose();
  m.material.dispose();
}
```

## Verificación

```bash
node --check --input-type=module < web/app.js   # sintaxis OK
docker compose up -d --build
curl -s http://localhost:8321/app.js | grep "if (!m) continue"  # servido
```

Recargar el navegador y soltar un STL: debe renderizar al primer intento.

## Lecciones

- Leer el stack ANTES de culpar al tamaño: `onLoad` alcanzado = parse OK =
  el problema está en NUESTRO callback, no en los datos.
- Al limpiar estado inicializable en `null` (o vacío), iterar con guardia —
  el "caso primero" siempre llega.
- Los assets estáticos van copiados en la imagen: tras tocar `web/` hay que
  `docker compose up -d --build`, no basta recargar.
