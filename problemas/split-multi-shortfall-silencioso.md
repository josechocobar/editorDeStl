# split_multi devolvía menos piezas sin avisar y con validación inconsistente

**Fecha:** 2026-08-25
**Proyecto:** STLFiles
**Rama/commit del fix:** master

## Síntoma

Pedir más partes de las que el modelo soporta (ej. 16 sobre una placa fina)
devolvía menos piezas **sin ninguna advertencia**: el usuario veía "5 piezas
generadas" sin saber que faltaban. Encontrado en auditoría de código, no por
reporte de usuario.

## Causa raíz

En `backend/mesh_ops.py` (`split_multi`):

1. Bloque `if len(nodes) < parts: pass` — código muerto literal que sugería
   un manejo del shortfall que nunca existió.
2. El loop corta con `break` cuando un corte produce mitades degeneradas
   (<12 caras), pero el resultado reducido salía igual de silencioso.
3. Validación inconsistente con `cut_half`: la operación hermana detecta
   "plano por aire" comparando volúmenes; `split_multi` solo contaba caras.

Nota honesta de alcance: el truncado `nodes[:parts]` NUNCA llega a cortar
(el loop crece exactamente una pieza por iteración) y los splits siempre
fueron consistentes con la lista devuelta — el riesgo de meta huérfano que
se sospechó al principio no existía. El defecto real era el silencio.

## Solución

- Guardia de corte fantasma en el loop (una cara vacía O volumen <0.1% del
  padre → mismo tratamiento que caras insuficientes), alineando criterios
  con `cut_half`.
- Bloque muerto eliminado; comentario documenta el contrato best-effort.
- La ruta `/api/cut` agrega warning `"Se generaron X de Y partes"` cuando
  hay shortfall — usa el plumbing de warnings ya visible en la UI.

## Verificación

```bash
python3 -m pytest -q    # 38 passed
```

Nuevos tests: `test_split_multi_shortfall_keeps_splits_consistent`,
`test_split_multi_air_cut_stops_cleanly` (dominio) y
`test_cut_multi_warns_on_parts_shortfall` (API, con splitter mockeado para
determinismo).

## Lecciones

- El shortfall silencioso viola el contrato implícito del resto del repo,
  donde toda degradación viaja en `warnings`. Ante dos operaciones hermanas,
  los criterios de validez deben ser los mismos.
- Un `pass` como cuerpo de `if` es un marcador de promesa incumplida: o se
  implementa lo que sugiere o se borra.
