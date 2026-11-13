# Inventario priorizado de defectos estratégicos HU/MW (2026-11-13)

**Estado:** inventario de auditoría. No implementa correcciones, no modifica
datos, no activa multiway y no declara cerrado ningún defecto.

**Base:** commit `8197eee`, `data/hands_db.jsonl` con SHA-256
`3f0e7e5e…8262e` (snapshot completo en
`DISCREPANCIAS_AUDITORIA_2026-11-13.md`).

**Instrumentos:** `tools/auditar_estrategia_reproducible.py`,
`DOCS/DISCREPANCIAS_AUDITORIA_2026-11-13.md`.

**Criterio de prioridad:** primero lo que cambia la acción o la etiqueta en HU;
después lo que cambia la estimación estadística; al final lo que solo afecta a
la arquitectura MW. Ningún defecto se cierra por reproducir una cifra: hacen
falta validación mecánica, estadística y estratégica.

## 1. Resumen

| ID | Clase | Prioridad | Defecto | Evidencia | Estado |
|---|---|---|---|---|---|
| D-01 | Mecánico | Crítica | Lectura preflop legacy y contrato no son la misma cosa | 6.233 etiquetas distintas; 468 es un par | Abierto verificado |
| D-02 | Mecánico | Crítica | `_preflop_spot` usa la última acción y no el estado relativo al hero | 2.365 `open→fold`; 1.580 `open→fold_vs_open`; 315 `limp→bb_check` | Abierto verificado |
| D-03 | Mecánico | Crítica | `_preflop_raises` no cuenta `b`; el limp de `_recom_preflop` solo mira `c` | 178 `b`; 162 >1 BB; 16 ≤1 BB; 183 diferencias de `n` | Abierto verificado |
| D-04 | Cobertura | Crítica | Tablas ausentes y fallback silencioso | 1.080 `Call_OR` sin cobertura; 78 `4B/Call_3B` missing; 69 fallback | Abierto verificado |
| D-05 | Estadístico | Alta | `FLAT_PRIOR` domina el prior | 1.881/2.396 (78,51 %); villanos 1.572/1.992 (78,92 %) | Abierto verificado |
| D-06 | Estadístico | Alta | El denominador de priors incluye al hero y se reporta como “villanos” | 2.396 incluye hero; 1.992 villanos | Abierto verificado |
| D-07 | Estadístico | Alta | Equity actual y equity a showdown se mezclan | Δ +13,0 / −11,1 / +12,3 pp; 100 vs 200 runouts | Abierto verificado |
| D-08 | Arquitectura | Crítica | La ruta live elige un solo villano; no hay equity multiway | `_villain_id` devuelve un PID; `n_players` solo llega a `rules.plan` | Abierto verificado |
| D-09 | Estratégico | Alta | `range_advantage`/`nut_advantage` son HU o aproximados | TODO F5; `nut_advantage` de una mano; `range_adv(sit.equity)` | Abierto verificado |
| D-10 | Arquitectura | Alta | `recommend_loop` combina rangos con `union()` | `_build_multiway_range` línea 185; etiqueta “no es equity multiway” | Abierto verificado |
| D-11 | Etiquetas | Alta | Entrenamiento legacy no coincide con el contrato | 54 distintas; 44 unresolved | Abierto verificado |
| D-12 | Estadístico | Media | `_perfil_for` clasifica por stack, no por estilo | media de stack o stake <50 BB → PEZ; sin datos → TIBURON | Abierto |
| D-13 | Mecánico | Media | `plan()` no filtra preflop y `recommend_loop` degrada a `rp=None` | `rules.py:572-574`; TODO F5 | Abierto |
| D-14 | Trazabilidad | Alta | No hay versión de datos/artefactos en el informe | hashes solo al ejecutar el script; datos dinámicos | Diseño pendiente |
| D-15 | Estadístico | Media | `DEFAULT_RUNOUTS=100` frente a 200 del informe | `decision.py:172`; sin IC declarado | Abierto |
| D-16 | Estratégico | Media | Tamaños multiway hardcodeados por `n_players` | `_multi_sizes` 0,33/0,50 y 0,50/0,66 | Abierto |

## 2. Tarjetas de los defectos que bloquean HU

### D-01 — Dos lecturas preflop incompatibles

- **Qué pasa:** la ruta live usa `_preflop_spot`/`_preflop_raises`; el contrato
  usa `first_decision`/`table_plan`. No son equivalentes.
- **Evidencia:** 6.233 diferencias de etiqueta. El “468” del informe es el par
  `(facing_open, call_open) -> (no_raise, limp)`, no el total.
- **Por qué importa:** cambia la tabla consultada (OR, ROL, 3B, Call_OR, 4B,
  Call_3B), y por tanto la frecuencia y la acción preflop.
- **Corrección propuesta:** una sola fuente de verdad para el estado preflop.
  La ruta live y el entrenamiento deben consumir la misma clasificación, con
  denominador, categoría, `raises_before`, `limps_before`, `vs_pos` y estado de
  cobertura.
- **Validación:** paridad mecánica por evento; inventario de diferencias;
  después validación estadística de frecuencias y estratégica de acciones.
- **Prohibido:** cambiar etiquetas o tablas para que el número cuadre.

### D-02 — `_preflop_spot` no representa el estado del hero

- **Qué pasa:** recorre las acciones del rival al revés y decide por la última
  acción; además, `fold`/sin acción cae en `open`. No distingue
  `fold_vs_open`, `fold_vs_3bet`, `bb_check`, `call_limp`, `squeeze` ni
  `rol`.
- **Evidencia:** los tres pares dominantes son 2.365 `(no_raise,open) ->
  (no_raise,fold)`, 1.580 `(no_raise,open) -> (facing_open,fold_vs_open)` y
  315 `(no_raise,limp) -> (no_raise,bb_check)`.
- **Por qué importa:** un fold del rival se interpreta como apertura; un check
  de BB se interpreta como limp; un call de limp se interpreta como call de
  open.
- **Corrección propuesta:** eliminar la heurística como fuente de decisión;
  sustituirla por el contrato contextual. Si se conserva como compatibilidad,
  debe ser una capa declarada y no la que elige tablas.
- **Validación:** tabla de confusión legacy→contrato; casos límite de `b`
  corto, `bb_check`, `limp`, `call_limp`, `fold` y `squeeze`.

### D-03 — `b` y limp corto no cuentan como agresión

- **Qué pasa:** `_preflop_raises` solo cuenta `r`. El recorder usa `b` para
  aperturas y también para limpes cortos de ≤1 BB. `_recom_preflop` detecta
  limp solo con `c`, no con `b` corto.
- **Evidencia:** 178 `b` crudas; 162 >1 BB; 16 ≤1 BB. `table_plan` vs
  `_preflop_raises` deja 183 diferencias de `n`, 177 de `vs`, 51 de limp y 6
  solo de `n`.
- **Por qué importa:** un `b` corto puede convertirse en “sin subida” y
  seleccionar OR/ROL en vez de 3B/4B; un `b` de apertura puede no contar como
  subida.
- **Corrección propuesta:** clasificar `b` por importe y contexto, no por
  letra. La ambigüedad debe quedar resuelta en el contrato, no en cada
  consumidor.
- **Validación:** matriz de acciones `b`/`r` por `raises_before`, `limps_before`
  y `vs_pos`; comparar la tabla elegida, no solo el conteo.

### D-04 — Cobertura preflop declarada pero no aplicada

- **Qué pasa:** el motor conoce tablas exactas y fallbacks, pero la decisión
  sigue usando `or 0.0` en varios caminos. No hay una regla de “sin cobertura =
  no recomendar” o “cobertura = incertidumbre”.
- **Evidencia:** 1.080 decisiones `facing_open` sin `Call_OR` (1.079 missing +
  1 fallback); 78 `facing_3bet` sin `4B` ni `Call_3B`; 69 con fallback
  `other_vs`.
- **Por qué importa:** una tabla ausente se convierte en frecuencia cero y
  puede producir un fold o un raise inventado.
- **Corrección propuesta:** devolver un estado de cobertura explícito
  (`exact`, `alias`, `coverage_gap`, `impossible`, `unclassified`) y decidir
  política: no recomendar, ampliar incertidumbre o usar un prior declarado.
  Nunca `or 0.0` silencioso.
- **Validación:** por spot, denominador, cobertura y acción resultante; casos
  con cobertura 0 no deben producir una acción presentada como exacta.

### D-11 — Etiquetas de entrenamiento y contrato

- **Qué pasa:** `preflop_events` conserva la categoría legacy; el contrato
  estricto clasifica otra cosa en 54 eventos y no resuelve 44.
- **Por qué importa:** el modelo aprende una distribución que no coincide con
  la que decide. Un AUC o una frecuencia pueden parecer válidos y describir
  otro problema.
- **Corrección propuesta:** declarar la etiqueta canónica, migrar el
  entrenamiento y conservar la legacy solo como compatibilidad auditada.
- **Validación:** paridad de etiquetas, matriz de confusión, recalibración por
  denominador. No declarar corregido por bajar una métrica agregada.

## 3. Tarjetas de los defectos estadísticos

### D-05/D-06 — Prior plano y denominador

- **Qué pasa:** `_prior_grid` devuelve `FLAT_PRIOR=0.15` cuando no hay tabla.
  El 78,5 % de los jugadores con acción postflop cae ahí.
- **Evidencia:** 1.881/2.396 (78,5058 %); villanos 1.572/1.992 (78,9157 %).
  Fuentes principales: `limp/BB` 313, `call_open/SB` 194, `call_open/BTN` 113,
  `call_open/CO` 109, `3bet/BTN` 92, `3bet/MP` 91.
- **Riesgo:** un prior plano no diferencia manos ni posiciones; si además se
  presenta como “rango del villano”, la incertidumbre desaparece.
- **Corrección propuesta:** prior por cobertura y por clase de spot; marcar
  `prior_source` y `effective_combos`; no normalizar el flat como si fuera una
  lectura observada.
- **Validación:** calibración por fuente; comparación contra baseline uniforme;
  intervalos por denominador; no usar el 78,5 % como si fuera evidencia de
  calidad.

### D-07 — Equity actual, showdown y EV

- **Qué pasa:** `situation.equity_vs_range` evalúa el board disponible (equity
  actual), mientras `decision.runout_equity` simula turn/river (showdown). El
  informe y algunos consumidores no separan ambos conceptos.
- **Evidencia:** flush draw 0,596207→0,726362; overpair 0,966235→0,855701;
  gutshot 0,181776→0,304762. El overpair baja 11 pp; el proyecto sube 13 pp.
- **Riesgo:** usar “equity” para dos cosas distintas; un EV construido sobre
  una mezcla no es comparable entre calles.
- **Corrección propuesta:** tres campos separados: `equity_current`,
  `equity_showdown`, `ev_by_action`; cada uno con `n_runouts`, `n_combos`, seed,
  intervalo y etiqueta de fuente.
- **Validación:** comparar Monte Carlo contra enumeración exacta cuando sea
  posible; error estándar; sensibilidad a seed; no comparar 100 con 200
  runouts sin declararlo.

### D-15 — Muestreo insuficiente o no declarado

- **Qué pasa:** `DEFAULT_RUNOUTS=100`, `DEFAULT_RUNOUT_COMBOS=200`. El informe
  usa 200 runouts. La diferencia de medias es pequeña, pero el error MC no se
  reporta.
- **Riesgo:** diferencias de 1–2 pp tratadas como estrategia cuando son ruido.
- **Corrección propuesta:** fijar `n_runouts` por caso, reportar error estándar
  o intervalo, y no aceptar una comparación sin denominador y semilla.

## 4. Tarjetas de arquitectura y estrategia

### D-08 — Un solo villano en la ruta live

- **Qué pasa:** `_villain_id` devuelve un PID: el agresor con mayor apuesta o,
  si no, el activo de mayor stack. La equity se calcula contra ese rango.
  `n_players` llega a `rules.plan`, pero no hay un conjunto de rangos rivales.
- **Evidencia:** `asistente_live.py:706`; `n_players` en `rules.plan`; métrica
  MW 399/894 (44,63 %) y fiable 210/506 (41,50 %) describen spots multiway,
  pero la política sigue siendo HU contra un rival.
- **Riesgo:** una recomendación multiway presentada como si fuera HU; la
  métrica MW mide exposición, no calidad de la decisión.
- **Corrección propuesta:** separar `hero`, `active_opponents`, `main_villain`
  y `range_set`; `n_players` no es suficiente. La política MW debe declarar
  “no soportada” o usar un modelo conjunto; nunca degradar en silencio a HU.
- **Validación:** introspección: todo spot `n_players>2` debe tener
  `multiway=True`, `multiway_soportado=False/True` explícito y jamás una
  equity etiquetada como HU.

### D-09 — Ventajas de rango y nuts aproximadas

- **Qué pasa:** `rules.plan` recibe `range_advantage` calculado como
  `range_adv(sit.equity)` y `nut_advantage` desde `hand_state`; ambos miran una
  mano/una equity HU. `rules.py:307` marca TODO F5.
- **Riesgo:** un tamaño o una línea MW se justifica con una ventaja que no es
  multiway.
- **Corrección propuesta:** definir `range_advantage` sobre el conjunto de
  rangos y `nut_advantage` sobre la distribución de nuts; si no hay datos,
  `unknown`, no `NEUTRAL` por defecto.
- **Validación:** ablación: misma decisión con y sin la ventaja; si no cambia,
  la variable no está haciendo nada. Y comparación contra rangos sintéticos
  controlados, no contra datos reales inflados.

### D-10 — `union()` no es un rango multiway

- **Qué pasa:** `_build_multiway_range` usa `combined.union(r)`; el docstring
  reconoce que suma masas y no normaliza, y que no es equity multiway.
- **Riesgo:** la probabilidad conjunta de varios rivales no es la unión de sus
  rangos; se pierde correlación y se sobreestima/ subestima la equity.
- **Corrección propuesta:** `MultiwayRangeSet` con un rango por rival, pesos,
  reach por acción, blockers compartidos y una operación de equity conjunta
  (producto o muestreo conjunto declarado). La unión solo puede quedar como
  baseline etiquetado.
- **Validación:** comparar contra simulación conjunta con un número fijo de
  rivales; test de que `n_players>2` nunca produce una etiqueta de “equity HU”.

### D-12 — Perfil del rival por stack

- **Qué pasa:** `_perfil_for` usa la media de stacks o el stake actual <50 BB
  para etiquetar PEZ; sin datos, TIBURON.
- **Riesgo:** el perfil no describe estilo; un jugador corto no es
  necesariamente PEZ, y el default oculta la ausencia de evidencia.
- **Corrección propuesta:** perfil con `source`, `n`, `confidence`; default
  `UNKNOWN` con rango amplio; no convertir un umbral de stack en estilo.
- **Validación:** calibración por perfil y por fuente; comparar contra perfil
  desconocido; no usar el perfil como verdad.

### D-13 — `plan()` no cubre preflop

- **Qué pasa:** `rules.plan` lanza `ValueError` para `street='preflop'`;
  `recommend_loop` lo captura y deja `rp=None`, perdiendo el filtrado de
  reglas. `_recom_preflop` es otra ruta.
- **Riesgo:** dos políticas preflop (matrices y reglas) sin contrato común.
- **Corrección propuesta:** decidir si preflop es una etapa propia del plan o
  una política separada con contrato explícito; no mezclar un `None`
  silencioso con “sin plan”.
- **Validación:** paridad de candidatos; todo spot preflop debe tener una
  fuente y un estado, no un `None` ambiguo.

## 5. Orden de ataque

1. **HU preflop:** D-01, D-02, D-03, D-04, D-11.
2. **Estimación:** D-05, D-06, D-07, D-15.
3. **Rutas:** D-13, D-12, D-14.
4. **MW:** D-08, D-10, D-09, D-16.
5. **Activación:** solo después de las validaciones del plan incremental.

## 6. Lo que no se puede concluir

- Reproducir una cifra no demuestra que la estrategia sea buena.
- Un test mecánico no demuestra calibración.
- Una mejora de EV en una muestra pequeña no demuestra mejora estratégica.
- Un `multiway_soportado=False` no es una decisión: es una ausencia declarada.
- Un `union()` etiquetado como “aproximado” sigue sin ser equity multiway.

## 7. Estado de cambios

No se ha modificado `motor/`, `data/` ni el informe original. Este inventario
solo abre defectos y propone validaciones; no implementa ninguna corrección.
