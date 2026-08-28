# Viewport panel con fondo transparente (var --card-bg inexistente)

**Fecha:** 2026-08-28
**Proyecto:** stlfiles

## Síntoma

El panel flotante de modelos sobre el viewport se veía transparente sobre el canvas: el texto y bordes flotaban sin fondo, dificultando la lectura sobre un modelo renderizado.

## Causa raíz

En `web/style.css` el selector `#viewport-panel` declaraba:

```css
background: var(--card-bg);
```

La variable `--card-bg` NO existe en `:root` — las variables definidas son `--bg`, `--panel`, `--card`, etc. Con `var()` sin fallback, la declaración queda inválida en computed-value time y la propiedad cae a su valor inicial (`transparent`).

## Solución

Reemplazar por la variable real que define el fondo de tarjetas:

```css
/* antes */
background: var(--card-bg);

/* después */
background: var(--card);
```

## Verificación

Inspección visual del panel en el viewport + chequeo de que `style.css` no referencie variables no definidas:

```bash
rg -o 'var\(--[a-z-]+' web/style.css | sort -u   # cruzar contra :root
```

## Lecciones

- Las variables de CSS no tienen validación en tiempo de escritura: un typo en el nombre no rompe el parseo, solo degrada la propiedad a su valor inicial de forma silenciosa.
- Al usar `var(--x)` sin fallback, verificar siempre que `--x` esté definida en `:root` (o agregar fallback explícito `var(--x, var(--card))`).