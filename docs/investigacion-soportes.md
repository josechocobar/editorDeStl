# Investigación — Generación de soportes para piezas cortadas

**Fecha:** 2026-08-23
**Estado:** esperando OK del usuario sobre qué tipos implementar
**Contexto del proyecto:** splitter STL (trimesh + manifold3d backend, three.js frontend).
Las piezas salen como STL independientes; los soportes se agregarían a cada pieza
ANTES del slicing, es decir, como geometría real unida por booleano (mismo enfoque
que ya usamos para conectores).

---

## 1. Detección de voladizos (común a todos los tipos)

Todo generador arranca igual: decidir QUÉ zonas necesitan soporte.

- **Por capa (slicers):** comparan el contorno de la capa N+1 contra la capa N.
  Todo lo que queda "en el aire" entre ambas es voladizo
  (PrusaSlicer `SupportCommon.cpp`, CuraEngine `ConicalOverhang.cpp`).
- **Por malla (nivel STL, el que aplica a nosotros):** una cara es voladizo si su
  normal apunta hacia abajo más allá de un umbral:
  `dot(normal_cara, [0,0,-1]) > cos(ángulo_limite)` (45° típico FDM, 20–30° resina).
  trimesh ya expone `mesh.face_normals`, así que esto es directo.
- Sobre las caras detectadas se **muestrean puntos de contacto** con separación
  mínima (grilla o clustering) y área mínima por punto, para no generar soportes
  en piquitos irrelevantes (MeshMixer llama a esto *minimum support area*).

Parámetros universales que aparecen en todos los proyectos:

| Parámetro | Qué controla | Default típico |
|---|---|---|
| Ángulo de voladizo | pendiente mínima que requiere soporte | 45–50° |
| Z-gap (contact distance) | aire entre soporte y pieza para poder desprender | 0.2–0.4 mm FDM |
| Diámetro de punta (tip) | contacto con la pieza, chico = menos marca | 0.4–1 mm |
| Densidad / distancia entre ramas | cuánto material bajo el voladizo | — |
| Interfaz (roof) | capa densa justo debajo del voladizo | opcional |

---

## 2. Tipos de soporte encontrados

### Tipo A · Pilares verticales simples

- **Referencia:** comportamiento base de MeshMixer (cerrado, pero su API está en
  https://github.com/meshmixer/mm-api y el flujo está bien documentado:
  Analysis → Overhangs → Generate Support) y el modo "pilares" de varios slicers.
- **Cómo se arma:**
  1. Detectar caras de voladizo y muestrear puntos de contacto.
  2. Desde cada punto, lanzar rayo vertical hacia abajo (`trimesh.ray`) hasta la
     cama virtual o hasta chocar con la propia pieza (apoyar ahí = menos altura).
  3. Generar un cilindro/cono desde el contacto hasta abajo, con punta cónica
     fina arriba y ensanche hacia la base.
  4. Unir todo a la pieza con booleano union (manifold3d, ya validado en este repo).
- **Pros:** trivial de implementar, rápido, robusto.
- **Contras:** muchos pilares independientes = más material y marcas; no colapsa
  ramas hacia un tronco común.
- **Dificultad con nuestro stack:** baja. Todo existe en trimesh
  (cilindros, ray casting, booleano manifold).

### Tipo B · Grid/enrejado bajo voladizos grandes

- **Referencia:** soportes "normales" de slicer — PrusaSlicer
  `src/libslic3r/Support/SupportMaterial.cpp`
  (https://github.com/prusa3d/PrusaSlicer/blob/master/src/libslic3r/Support/SupportMaterial.cpp)
  y CuraEngine `src/support.cpp`
  (https://github.com/Ultimaker/CuraEngine/blob/main/src/support.cpp).
- **Cómo se arma (idea slicer, adaptada a malla):**
  1. Detectar regiones de voladizo planas (grandes áreas casi horizontales).
  2. Proyectar esa región hacia abajo hasta la base, generando un prisma hueco.
  3. Rellenar ese volumen con paredes cruzadas (patrón grid/zig-zag) en vez de
     sólido: se logra extruyendo el contorno y restando el mismo volumen
     encogido, dejando paneles cruzados.
  4. Capa de interfaz densa (techo fino) pegada al voladizo con Z-gap.
- **Pros:** ideal para techos planos grandes (justo el caso de piezas cortadas:
  la cara de corte siempre es plana); muy estable.
- **Contras:** consume bastante material; difícil de quitar sin interfaz;
  feo en figuras orgánicas.
- **Dificultad:** media. La parte geométrica (prisma con paneles internos) hay
  que construirla a mano con trimesh, pero son operaciones de extrusión/resta
  conocidas.

### Tipo C · Árbol clásico estilo Cura (colapso hacia abajo)

- **Referencia:** CuraEngine histórico (v4.x, `treeSupport.cpp`; hoy reemplazado),
  descripto en el fork de Thomas Rahm y discusiones de Ultimaker.
- **Cómo se arma:**
  1. Puntas (círculos chicos) sobre cada zona de voladizo.
  2. Bajar capa por capa: cada punta se convierte en un nodo que se desplaza en
     XY buscando llegar a la cama o apoyarse en el modelo, usando mapas de
     **evitación** ("avoidance"): zonas donde el centro de la rama NO puede estar
     en cierta altura sin chocar la pieza, calculados desde abajo hacia arriba
     con el radio actual de rama.
  3. El radio crece al bajar (ramas gruesas abajo); cuando dos ramas se
     acercan, se fusionan (merge) reduciendo retracciones y material.
- **Pros:** menos material que pilares individuales; buen compromiso.
- **Contras:** el algoritmo original era lento y generaba ramas gordas pegadas
  al modelo.
- **Dificultad:** alta para nosotros — está pensado para trabajar POR CAPAS
  (2.5D). Adaptarlo a malla pura significa rehacerlo sobre slices horizontales
  (factible: `mesh.section()` de trimesh da los cortes por altura, pero es un
  proyecto grande).

### Tipo D · Árbol V2 / Orgánico (estado del arte)

- **Referencias (todas verificadas):**
  - Reimplementación de Thomas Rahm: https://github.com/ThomasRahm/CuraEngine
    (el README tiene la explicación visual completa del algoritmo).
  - Integrada oficialmente en CuraEngine moderno:
    `src/TreeSupport.cpp`, `src/TreeModelVolumes.cpp`,
    `src/TreeSupportTipGenerator.cpp`, `src/TreeSupportElement.cpp`
    (https://github.com/Ultimaker/CuraEngine/tree/main/src)
  - Base de "Organic supports" de PrusaSlicer 2.6+:
    `src/libslic3r/Support/OrganicSupport.cpp` y `TreeModelVolumes.cpp`
    (https://github.com/prusa3d/PrusaSlicer/tree/master/src/libslic3r/Support)
- **Cómo se arma (4 fases según el propio autor):**
  1. **Evitaciones (bottom-up):** mapas por capa de zonas prohibidas para
     centros de rama, en variantes (lento/rápido, hacia cama/hacia modelo,
     con/sin agujeros), precalculadas en paralelo.
  2. **Áreas de influencia (top-down):** desde cada punto de voladizo crece un
     área que representa dónde puede estar el centro de la rama que lo cubre.
     Cuando dos áreas de influencia se intersecan, se fusionan → eso ES la
     ramificación: búsqueda geométrica en anchura con fusión golosa (greedy).
  3. **Trayectoria del árbol (bottom-up):** con las áreas fusionadas se eligen
     los centros de los círculos que forman cada rama, respetando ángulo
     preferido de rama (estable) y ángulo máximo (solo si hace falta esquivar).
  4. **Dibujo:** se dibujan los círculos (sección circular garantizada),
     puntas finas arriba, diámetros crecientes abajo, doble pared automática
     donde la rama es gruesa (PrusaSlicer).
- **Pros:** ~70–80% menos material que grid; fácil de sacar; llega a lugares
  difíciles; es el estándar actual (Cura 5.3+, PrusaSlicer, Bambu/Orca).
- **Contras:** complejidad alta; consumo de RAM; pensado para dominio por capas.
- **Dificultad para este proyecto:** muy alta como port completo; media-alta
  como versión simplificada (ver recomendación).

### Tipo E · Ramificación a nivel malla (estilo SLA / paper "Clever Support")

- **Referencias:**
  - Paper: *Clever Support: Efficient Support Structure Generation for Digital
    Fabrication* (Vanek et al., 2014) — citado como base por PrusaSlicer.
  - Implementación abierta a nivel malla (la más parecida a lo que necesitamos):
    PrusaSlicer SLA — `src/libslic3r/SLA/SupportPointGenerator.cpp` (detecta
    puntos de apoyo sobre la malla) y `src/libslic3r/SLA/DefaultSupportTree.cpp`
    + `SupportTreeMesher.cpp` (construye pilares y ramas COMO GEOMETRÍA:
    cápsulas y conos entre puntos, con union final)
    (https://github.com/prusa3d/PrusaSlicer/tree/master/src/libslic3r/SLA)
- **Cómo se arma:**
  1. Muestrear puntos de apoyo sobre la malla (voladizos + criterios de
     estabilidad: puntos altos sin nada debajo).
  2. Cada punto recibe un "pinhead" (punta troncocónica con disco de contacto).
  3. Bajar en línea recta si no hay colisión; si la hay, buscar ruta con
     desvíos (el paper original usa consultas esféricas precalculadas para
     esquivar el modelo baratísimo).
  4. Las columnas cercanas se unen en troncos comunes hacia la base
     (branching), y toda la estructura se genera como mallas primitivas
     (conos/cápsulas) y se une por booleano.
- **Pros:** trabaja directamente sobre STL (nuestro dominio exacto); salida =
  unión de primitivas, que es EXACTAMENTE lo que ya hacemos con conectores;
  resultado liviano tipo árbol sin necesidad de slices por capa.
- **Contras:** orientado a resina en origen (hay que endurecerlo para FDM:
  grosores mayores, Z-gap mayor, bases más anchas).
- **Dificultad:** media. Es la arquitectura natural para nuestro backend.

---

## 3. Comparativa rápida

| Tipo | Material | Facilidad de sacar | Complejidad de implementación aquí | Ideal para |
|---|---|---|---|---|
| A · Pilares simples | alto | media | ★ baja | primer hit funcional |
| B · Grid plano | alto | difícil sin interfaz | ★★ media | caras de corte planas |
| C · Árbol Cura v1 | medio | media | ★★★★ alta (dominio por capas) | histórico |
| D · Árbol/orgánico | bajo | fácil | ★★★★★ muy alta | figuras orgánicas |
| E · Ramas a nivel malla | bajo | fácil | ★★★ media | nuestro caso de uso |

## 4. Recomendación técnica → DECISIÓN

**Elegido: combo A+E** (aprobado por el usuario, ver reglas en sección 5).

Arquitectura tipo E (a nivel malla, primitivas + booleano) construyendo árboles
que nacen de una base común, con la simplicidad de A donde una columna recta
alcanza sin colisión. B queda como segundo paso opcional para techos planos
grandes. C y D descartados para este proyecto.

## 5. Reglas del proyecto — soportes para minis

Casos de uso principal: **miniaturas** (figuras pequeñas con voladizos finos:
armas, capas, brazos, picos). Estas reglas son VINCULANTES para la
implementación; cualquier cambio se negocia acá antes que en código.

### 5.1 Estructura

- **R1 · Árbol desde base común.** Todas las ramas nacen de una base/pad común
  bajo la pieza (estilo pad de resina / MeshMixer). Prohibido dejar columnas
  independientes cayendo directo a la cama salvo que estén fuera del alcance
  del árbol.
- **R2 · Fusión hacia abajo.** Las columnas cercanas entre sí (umbral a definir,
  ~2–4 mm entre centros) se fusionan en una rama común a medida que bajan.
  El tronco resultante engrosa con cada fusión y con la profundidad.

### 5.2 Dimensiones

- **R3 · Rama fina pero sólida: 0.8 mm de diámetro en las puntas** (decisión del
  usuario; coincide con el default de Cura Tree Tip Diameter = 0.8 mm).
  Engrosamiento progresivo hacia abajo, p. ej. +0.4 mm por cada 10 mm de altura
  o por fusión (afinar empíricamente).
- **R4 · Punta de contacto cónica y chica** (0.4–0.6 mm de disco) para marcar
  lo menos posible la mini. Z-gap configurable: FDM ≈ 0.2 mm (1 capa);
  resina ≈ contacto casi directo.
- **R5 · Base sólida pero contenida:** disco/plancha de ~1–1.5 mm de espesor,
  extendida apenas más allá de los troncos que llegan a ella. No cubrir toda
  la huella de la pieza si no hace falta.

### 5.3 Comportamiento

- **R6 · Apoyo preferente en el propio modelo** cuando el rayo vertical choca
  con la pieza a poca distancia (menos altura = menos material = rama más
  corta). Opción "solo cama" como toggle futuro.
- **R7 · Ángulo de voladizo default 45°**, ajustable por request de API.
  En minis conviene subirlo a ~50–55° para no llenar de soportes pliegues
  que aguantan solos.
- **R8 · Separación entre puntas sobre el voladizo: ~1.5–2 mm** (las minis
  tienen features chicas; separaciones grandes dejan techo colgado).
- **R9 · Todo el soporte se genera orientado a -Z** sobre la pieza YA cortada;
  no reorientamos nada: la impresión es como queda el splitter.
- **R10 · Unión por booleano manifold3d** (mismo pipeline validado de
  conectores). La pieza final debe seguir siendo watertight — verificar con
  `is_watertight` después de la unión, igual que hacemos con conectores.

## 6. Referencias (verificadas 2026-08-23)

- ThomasRahm/CuraEngine — README con el algoritmo Tree Support V2 explicado:
  https://github.com/ThomasRahm/CuraEngine
- Ultimaker/CuraEngine (implementación oficial moderna):
  https://github.com/Ultimaker/CuraEngine/tree/main/src
  (`TreeSupport.cpp`, `TreeModelVolumes.cpp`, `TreeSupportTipGenerator.cpp`, `support.cpp`)
- PrusaSlicer FDM (orgánico + normal):
  https://github.com/prusa3d/PrusaSlicer/tree/master/src/libslic3r/Support
  (`OrganicSupport.cpp`, `TreeModelVolumes.cpp`, `SupportMaterial.cpp`, `SupportCommon.cpp`)
- PrusaSlicer SLA (soportes a nivel malla, basados en Clever Support):
  https://github.com/prusa3d/PrusaSlicer/tree/master/src/libslic3r/SLA
  (`SupportPointGenerator.cpp`, `DefaultSupportTree.cpp`, `SupportTreeMesher.cpp`)
- MeshMixer API (flujo de generación de soportes):
  https://github.com/meshmixer/mm-api
- Paper Clever Support (Vanek et al., 2014):
  https://www.researchgate.net/publication/264549729_Clever_Support_Efficient_Support_Structure_Generation_for_Digital_Fabrication
