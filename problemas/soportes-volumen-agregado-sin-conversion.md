# Volumen agregado por soportes reportado en mm³ con etiqueta de cm³

**Fecha:** 2026-08-23
**Proyecto:** STLFiles
**Rama/commit del fix:** feat/soportes-minis (pendiente de commit)

## Síntoma

En el smoke test sobre `samples/esfera.stl` el meta reportaba
`+535.35cm3` de volumen agregado por los soportes, cuando la pieza entera
mide ~14 cm³. Los soportes no podían pesar 38 veces la pieza. El número
parecía indicar una unión booleana rota (geometría inflada).

## Causa raíz

Error de unidades en `backend/supports.py` (`add_supports`). `trimesh`
devuelve `mesh.volume` en unidades del modelo (mm para STL), pero la clave
del meta se llama `added_volume_cm3` y no había conversión:

```python
# antes
info["added_volume_cm3"] = round(abs(out.volume) - abs(piece.volume), 2)

# después
info["added_volume_cm3"] = round((abs(out.volume) - abs(piece.volume)) / 1000.0, 2)
```

El delta real era 14 551 − 14 016 = **535 mm³ = 0,54 cm³**: correcto.
La geometría nunca estuvo rota; el bug era solo del meta.

## Solución

División por 1000 en la línea del cálculo (backend/supports.py:270). No se
tocó ninguna operación booleana ni generación de sólidos.

## Verificación

```bash
python3 - <<'EOF'
from backend import mesh_ops, supports
spec = {"angle":50,"tip_diameter":0.8,"contact_diameter":0.5,
        "spacing":1.8,"z_gap":0.2,"base_thickness":1.2}
m = mesh_ops.load_mesh("samples/esfera.stl")
out, info = supports.add_supports(m, spec)
print(info["added_volume_cm3"])   # → 0.54
EOF
```

Además: `pytest -q` completo en verde (27 passed).

## Lecciones

- Cuando un delta de volumen sea absurdamente grande o chico, verificar
  UNIDADES antes de sospechar de la geometría: mm³ vs cm³ es 3 órdenes de
  magnitud y trimesh no convierte nada automáticamente.
- Nombrar claves de meta con la unidad explícita (`_cm3`) solo sirve si hay
  un único punto de conversión y testeado; si no, el nombre miente igual.
