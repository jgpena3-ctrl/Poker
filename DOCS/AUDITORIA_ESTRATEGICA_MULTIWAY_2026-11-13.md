# Auditoría estratégica y diseño Multiway

**Fecha:** 2026-11-13  
**Repositorio:** `C:\Users\Usuario\Documents\Repos\Poker`  
**HEAD:** `8197eee` (`f0 congelado`)  
**Árbol:** limpio (`git status --short` vacío)  
**Alcance:** auditoría de solo lectura del motor estratégico, de las rutas live y del estado real de los datos/modelos. No se ha modificado código, datos, modelos, manifiestos ni pins. No se ha hecho commit ni staging. No se ha ejecutado `--apply` ni ningún writer real. `MULTIWAY_SOPORTADO` sigue en `False`.

**Cómo leer este informe**

- **[HECHO]**: medido directamente en código, datos o estado del repo.
- **[HIPÓTESIS]**: inferencia razonable, pendiente de medición específica.
- **[PROPUESTA]**: diseño o decisión recomendada, no implementada.

> **Verificación posterior read-only (2026-11-13).** El instrumento
> `tools/auditar_estrategia_reproducible.py` reproduce la base y detecta
> discrepancias en este informe. En particular: **468 no es el total** de
> divergencias de `_preflop_spot` (es un par; el total es **6.233**);
> **431/37 no reproducen** (dan **211/177/6**); la distribución de
> `table_plan` no es 3.065/1.563/2.329/147/3 (da **5.355/812/915/23/2**); y
> el denominador 2.396 incluye al hero (villanos: **1.992**). Las cifras de
> este informe no deben citarse sin leer
> `DOCS/DISCREPANCIAS_AUDITORIA_2026-11-13.md`. El informe se conserva como
> registro histórico; no se reescriben sus cifras.

> Este informe no declara cerrado F0 ni certifica la base. El contrato F0 marca D1 como `PARTIAL` y deja D1 completo pendiente de reauditoría independiente (`DOCS/F0_CONTRATO_INTEGRIDAD_ESCRITURA.md`, tabla final). Además, los artefactos de rangos postflop y perfil declaran `arbol_sucio: true` y `code_commit: 0fcceed`, distinto del HEAD actual. Por tanto, cualquier cifra de calidad de este informe es provisional y no debe usarse como evidencia de producción certificada.

---

## 0. Resumen ejecutivo

1. **[HECHO] El multiway ya es una parte central de las decisiones reales.** Sobre las 877 manos fiables, `multiway.metrica_politica()` mide 210 de 506 decisiones no-fold del hero en multiway (41,5%; techo 234, 46,2%). Sobre las 1.344 manos totales mide 399 de 894 (44,6%). La ruta live, sin embargo, sigue calculando equity heads-up contra **un solo** rival.
2. **[HECHO] La ruta de producción no usa el contrato preflop estricto.** `asistente_live._preflop_raises()` solo cuenta acciones `r`, mientras que las aperturas aparecen codificadas como `b` en una parte de la base y como `r` en otra. Resultado medido: 468 de 7.107 primeras decisiones preflop difieren del plan estricto; 434 corresponden a una apertura `b` leída como “sin raise” y resuelta con tabla `OR`.
3. **[HECHO] La etiqueta preflop que alimenta el rango postflop del rival es inestable.** En 2.396 jugadores activos con acciones postflop, la heurística legacy `_preflop_spot` y el contrato estricto solo coinciden en 702 (29,7%). 454 jugadores son etiquetados `3bet` por la ruta legacy cuando el contrato lee apertura, rol o limp.
4. **[HECHO] El prior posicional de rango falta en la mayoría de los casos.** En 1.881 de 2.396 villanos activos postflop (78,5%) no hay tabla posicional para el prior y se usa `FLAT_PRIOR=0.15`. En acciones sin tabla (por ejemplo `limp`, o `Call_OR`/`3B` sin par), ese prior plano se expande a los 1.326 combos y, tras normalizar, domina la masa: medido, el rango efectivo queda en 759–949 combos equivalentes, es decir, casi uniforme.
5. **[HECHO] Faltan tablas que hacen imposible una acción.** En el plan estricto hay 2.329 spots “facing open”; en 1.080 (46,4%) no existe tabla `Call_OR`, de modo que el modelo solo puede subir o retirarse. `Call_OR` solo existe para BB (5 rivales) y BTN (UTG/MP/CO). Además, 78 decisiones de 4-bet no tienen ninguna de las dos tablas (`4B`/`Call_3B`).
6. **[HECHO] La equity que ve el panel y consumen las reglas no es equity real en flop/turn.** `situation.equity_vs_range()` evalúa la fuerza actual de las 5 cartas, sin sortear turn/river. Medido contra un rango uniforme: el proyecto de color pasa de 0,596 a 0,726 (Δ +0,130) y la overpair de 0,966 a 0,856 (Δ −0,110). `compute_evs()` sí sortea runout, pero solo para las acciones; el `check` sigue asumiendo que no hay apuestas futuras.
7. **[HECHO] El modelo de respuesta es poblacional y con soporte escaso.** El Oracle tiene 143 celdas; 58 (40,6%) tienen `n < 20`; la mediana es 29. Con `returned_n = 0`, `OracleResponse` usa la heurística pura. En live solo se usan dos perfiles (`PEZ`/`TIBURON`) elegidos por stack; el ajuste individual `omega` existe pero no se usa en `asistente_live`.
8. **[HECHO] El único constructor multiway del repo viola el contrato.** `recommend_loop._build_multiway_range()` usa `RangeState.union()` y `compute_evs()` sobre el pool, lo que equivale a equity heads-up contra un rival muestreado del pool, no equity de campo. No es la ruta live (que ni siquiera construye rangos múltiples), pero sigue disponible y no debe usarse como base.
9. **[HECHO] F0 y la procedencia no están cerrados.** D1 `PARTIAL`; artefactos con árbol sucio y commit anterior; la reauditoría previa de F0 reportó bypasses con subclases de primitivos. No se revalidan aquí. Cualquier plan que dependa de “datos limpios” queda bloqueado hasta cerrar esa dependencia.
10. **[PROPUESTA] Orden recomendado:** congelar cualquier activación MW; corregir primero la lectura preflop y la equity/prior HU; construir después un sampler conjunto de campo en sombra; validarlo con casos exactos y con reducción a HU; y solo entonces abrir recomendaciones MW con confianza y límites explícitos.

---

## 1. Estado real del repositorio y documentación

### 1.1 Estado del repo

**[HECHO]**

- HEAD: `8197eee f0 congelado`.
- Árbol limpio; sin cambios locales.
- `MULTIWAY_SOPORTADO = False` en `motor/rules.py:48`.
- Política vigente: `POLITICA_MULTIWAY = 'F7.2.b/hu-contra-un-rival'` (`rules.py:53`).
- Motivo declarado: el motor solo tiene equity HU contra un rival (`rules.py:56-58`).

### 1.2 Datos y artefactos

| Artefacto | Tamaño / estado | Lectura |
|---|---:|---|
| `data/hands_db.jsonl` | 2.070.355 bytes | 1.344 manos cargadas; 877 fiables (`reliable_only=True`) |
| `data/preflop_matrices.json` | 328.548 bytes | 117 tablas; 107 exactas, 1 alias, 2 ausencias intencionales, 30 huecos de cobertura |
| `data/behavior.json` | 27.908 bytes | 877 manos, 8.742 observaciones, 143 celdas Oracle |
| `data/postflop_ranges.json` | 13.709 bytes | 866 manos usadas; `alpha=2.0`; 5 buckets; `arbol_sucio:true`; `code_commit:0fcceed` |
| `data/profile_ranges.json` | 90.334 bytes | 866 manos usadas; `alpha=2.0`; `arbol_sucio:true`; `code_commit:0fcceed` |
| `data/decisions.jsonl` | 8.903.510 bytes | decisiones registradas; no auditado aquí para leakage |
| `data/observations.json` | 4.738.786 bytes | observaciones; no auditado aquí para leakage |

**[HECHO]** Los metadatos de `postflop_ranges.json` y `profile_ranges.json` declaran `arbol_sucio: true` y `code_commit: 0fcceed`. No coinciden con el HEAD `8197eee`. Esto no prueba que los números estén mal, pero sí impide tratarlos como artefactos reproducibles del commit actual.

### 1.3 Documentación relevante

- `DOCS/CONTRATO_F72A.md`: contrato de la política multiway; prohíbe `RangeState.union()` como atajo.
- `DOCS/F0_CONTRATO_INTEGRIDAD_ESCRITURA.md`: D1 `PARTIAL`; D1 completo pendiente de reauditoría independiente.
- `DOCS/AUDITORIA_MATRIX.md`: H3 documenta la convención “tabla ausente = frecuencia 0” y H5 deja reservada la semántica estadística de la celda.
- `DOCS/AUDITORIA_PIPELINE_MODELOS_LIVE.md`, `DOCS/AUDITORIA_CONTRATOS_DERIVADOS.md`, `DOCS/AUDITORIA_TRANSVERSAL_P0.md`: auditorías previas del pipeline y contratos; se usan como contexto, no como evidencia nueva.
- `DOCS/ARQUITECTURA.md`: mapa general del motor.

### 1.4 Tests que fijan el comportamiento actual

**[HECHO]** Existen tests que fijan explícitamente la política y las convenciones actuales, entre ellos:

- `motor/test_multiway_soportado.py`: exige `MULTIWAY_SOPORTADO is False`; exige que el flag no cambie la acción; prohíbe `union()`.
- `motor/test_lectura_matrices.py`: fija que la ausencia de tabla se lee como 0 y que `None` y `0.0` son distintos.
- `motor/test_preflop_contract.py`: compara la lectura legacy con el contrato estricto; el contrato sigue en sombra.
- `motor/test_asistente_live.py`, `motor/test_decision.py`, `motor/test_player_ranges.py`, `motor/test_postflop_ranges.py`: cubren la ruta live, EV, rangos y perfiles.

**No se ejecutó la suite completa** durante esta auditoría. Las cifras de este informe son mediciones read-only sobre código y datos.

---

## 2. Mapa de la arquitectura estratégica

### 2.1 Flujo de datos y decisión

```
hands_db.jsonl
  ├─ learn.preflop_events (legacy) ──> ProfileRangeModel (preflop, por perfil)
  ├─ behavior.build / Oracle      ──> P(A|C) postflop
  └─ observations.extract_hands   ──> PostflopRangeModel (P(A|H), 5 buckets)
preflop_matrices.json (estático)  ──> OR/ROL/3B/Call_OR/4B/Call_3B/5B/...
```

**Ruta live de producción (`motor/asistente_live.py`):**

1. Estado OCR + recorder (`self.rec.hand`, `state`).
2. Preflop: `_preflop_spot()` para el rival, `_preflop_raises()` para el hero, `_pf_table_lookup()`/`_pf_freq()` sobre `preflop_matrices.json`, `_pf_evs()` y `_sample_preflop_action()`.
3. Postflop: `_villain_id()` elige **un** rival; `_perfil_for()` asigna `PEZ`/`TIBURON` por stack; `range_model.prob_vec(perfil, spot, action, ...)` construye un `RangeState`; `_villain_postflop_actions()` actualiza con `postflop_model.prob_vec(...)`.
4. `situation()` calcula `equity` con `equity_vs_range()` (estática en flop/turn).
5. `hand_classify()` calcula rol y `nut_advantage()`; `rules.plan()` filtra candidatos y sizings; `compute_evs()` calcula EV (runout sí/no); `rules.select_best()` elige.
6. Jerarquía y `equity_main` se calculan en modo sombra y **no** cambian la acción (`hierarchy.py`, `asistente_live._jerarquia`, `_equity_main_sombra`).

**Ruta de análisis/demo (`motor/recommend_loop.py`):**

- Construye un rango por villano con `_build_villain_range()`.
- Si recibe varios rangos, usa `_build_multiway_range()` → `RangeState.union()` → `compute_evs()` sobre el pool.
- No es la ruta que corre en producción; los tests lo dicen expresamente (`test_multiway_soportado.py`).

**Ruta de contrato (`motor/preflop_contract.py`):**

- `first_decision()`, `table_plan()`, `walk_preflop(legacy=False)`.
- Es la lectura estricta y se ejecuta en sombra; **no** elige tabla ni acción en producción.

### 2.2 Fuentes únicas y divergencias

| Concepto | Fuente única declarada | Uso real |
|---|---|---|
| Flag multiway | `rules.RulePlan.multiway` / `multiway_soportado` | Live y demo lo leen; live no cambia la acción |
| Pesos de rango | `ranges.villain_weights` | `situation` y `decision` comparten |
| Tablas preflop | `preflop_matrices.json` | Live, ProfileRangeModel y contrato tienen lectores distintos |
| Etiqueta preflop | `learn.preflop_events` (legacy) | Entrena `ProfileRangeModel`; live usa `_preflop_spot`; contrato usa `first_decision` |
| Oracle | `behavior.Oracle` | `PostflopRangeModel` lo recibe inyectado en `build_models`; `load()` no lo restaura |
| Selección | `rules.select_best` | Live y demo; no consulta `multiway_soportado` |

**[HECHO]** Hay tres lecturas preflop distintas: `learn.preflop_events` (entrenamiento), `asistente_live._preflop_spot`/`_preflop_raises` (serving) y `preflop_contract.first_decision`/`table_plan` (sombra). No son equivalentes; la sección 3 lo cuantifica.

---

## 3. Auditoría de la lógica preflop

### 3.1 Inventario y cobertura de tablas

**[HECHO]** `preflop_matrices.json` contiene 117 tablas:

- `OR`: 5 (sin BB).
- `ROL`: 5 (sin UTG).
- `3B`, `4B`, `5B`, `Call_OR`, `Call_3B`, `Call_4B`, `Call_5B`: 15 cada una (pares ordenados compatibles).
- `Call_OR`: solo 8 (BB vs 5; BTN vs UTG/MP/CO).
- `SQUEEZE`: 6; `Over_Call`: 3.

**[HECHO]** `preflop.audit_engine_coverage()` clasifica:

- 107 consultas exactas.
- 1 alias (`4B_UTG_vs_MP` → `4B_UTG_vs_HJ`).
- 2 ausencias intencionales.
- 30 huecos de cobertura (`coverage_gap`): 20 de la familia `Call_*` y 10 de `4B`.
- 0 sin clasificar.

### 3.2 La codificación `b`/`r` rompe la lectura del spot

**[HECHO]** En la base, la primera acción agresiva de una mano se codifica de dos formas:

- `b` en 175 manos (mediana de importe 2,5 en el primer agresor sin limps).
- `r` en 767 manos (mediana 2,5 en el primer agresor sin limps).

Es decir, una apertura puede venir como `b` o como `r`. `asistente_live._preflop_spot()` trata `b` como `open` y `r` como `3bet`; `_preflop_raises()` solo cuenta `r`. La combinación produce dos errores distintos:

1. Una apertura `b` no incrementa `n_raises`; el hero la lee como “sin raise” y consulta `OR` en vez de `3B`/`Call_OR`.
2. Una apertura `r` sí incrementa `n_raises`, pero para el rango postflop del rival `_preflop_spot()` la etiqueta como `3bet`.

**[HECHO] Medición sobre 7.107 primeras decisiones preflop:**

| Comparación legacy vs plan estricto | Decisiones |
|---|---:|
| Sin diferencias | 6.639 |
| Difieren en `n_raises` y `vs_pos` | 431 |
| Difieren solo en `n_raises` | 37 |
| **Total con diferencia** | **468 (6,6%)** |

De las 474 decisiones con una apertura `b` previa de importe > BB:

- 434 se leen con `n_raises = 0` (deberían ser `n_raises = 1`).
- 37 se leen con `n_raises = 1` (deberían ser `n_raises = 2`).
- 3 quedan en un estado ambiguo.

### 3.3 Cobertura en spots “facing open”

**[HECHO]** El plan estricto reparte las 7.107 decisiones así:

| Plan estricto | Decisiones |
|---|---:|
| `OR` | 3.065 |
| `ROL` | 1.563 |
| `3B`/`Call_OR` (facing open) | 2.329 |
| `4B`/`Call_3B` | 147 |
| No resuelto | 3 |

De los 2.329 spots facing open:

| Cobertura `3B` / `Call_OR` | Decisiones |
|---|---:|
| Exacta / exacta | 1.249 |
| Exacta / ausente | 1.079 |
| Fallback / ausente | 1 |
| **Sin tabla de call** | **1.080 (46,4%)** |

Consecuencia [HECHO]: en esos 1.080 spots el modelo solo puede recomendar `subir` o `retirar`; `igualar` es estructuralmente imposible. `Call_OR` solo existe para BB (todos los rivales) y BTN (UTG/MP/CO). CO, SB, MP y UTG no tienen tabla de call contra una apertura en ningún par completo.

**[HECHO]** En 4-bet, 78 de 147 decisiones tienen ambas tablas ausentes y 69 tienen ambas en `fallback_other_vs`; no hay ningún caso exacto/exacto en la muestra medida. Esto deja el 4-bet esencialmente sin soporte de tabla.

### 3.4 La convención “tabla ausente = 0”

**[HECHO]** `asistente_live._pf_freq()` devuelve `None` si no hay tabla; los llamadores hacen `or 0.0`. En `_recom_preflop()`:

- `n_raises == 1`: `f_r = _pf_freq('3B', ...) or 0.0`, `f_c = _pf_freq('Call_OR', ...) or 0.0`; si ambas faltan, `_pf_evs(0, 0)` devuelve `{'retirar': 1.0, 'igualar': 0.0, 'subir': 0.0}`.
- `n_raises >= 5`: `{'retirar': 1.0, ...}` directo.

**[HECHO]** Esta convención está fijada por tests (`test_lectura_matrices.py`, `test_recom_preflop_sb_no_pide_call_sin_tabla`) y documentada en `AUDITORIA_MATRIX.md` (H3). No es un bug de implementación; es una decisión declarada. Pero su consecuencia estratégica es crítica: **una ausencia de dato se convierte en un fold determinista**, no en “no hay recomendación” ni en una acción de confianza baja.

### 3.5 Selección de acción: muestreo, no argmax

**[HECHO]** `_sample_preflop_action()` muestrea la distribución `{subir, igualar, retirar}` con `random.Random(seed)`; no elige el argmax. El comentario del módulo lo declara: “la estrategia sigue siendo probabilística”. La semilla se registra para reproducibilidad.

**Implicaciones [HIPÓTESIS]:**

- Dos instancias idénticas pueden recibir recomendaciones distintas.
- La acción mostrada como “Mejor acción” es la acción muestreada, no la de mayor frecuencia.
- En spots con frecuencia casi empatada, el muestreo amplifica el ruido de las tablas.
- Para un asistente, esto puede ser deseable si se busca una estrategia mixta; para un producto que promete “la mejor acción”, es una decisión de producto no validada.

### 3.6 `_pf_evs`: independencia y reescalado

**[HECHO]** `_pf_evs(f_raise, f_call)` suma las dos frecuencias; si superan 1, las escala proporcionalmente y deja `retirar = 1 - fr - fc`. Si suman menos de 1, el resto es fold.

**Riesgo [HIPÓTESIS]:** las tablas de `3B` y `Call_OR` se estiman por separado; no hay garantía de que sus frecuencias sean mutuamente excluyentes para la misma mano. El reescalado es una convención, no una derivación probabilística. Debe validarse contra la frecuencia observada de cada acción en la base.

### 3.7 Tablas que no se usan en live

**[HECHO]** `_recom_preflop()` no consume `SQUEEZE` ni `Over_Call`. `_preflop_spot()` tampoco devuelve `squeeze`; devuelve `open`, `3bet`, `call_open` o `limp`. Por tanto:

- Las 6 tablas `SQUEEZE` y las 3 `Over_Call` no participan en la recomendación live.
- Los spots de squeeze se resuelven con `3B`/`Call_OR` o con `4B`, según el conteo de `r`, no con la tabla específica.

### 3.8 Posición desconocida y fallbacks

**[HECHO]** En `_recomendacion_para()`: `villain_pos = self._pos_of(villain, state) or 'UTG'`. Si el OCR no resuelve la posición del rival, se asume UTG. Esto sesga el rango y el prior hacia la posición más temprana.

**[HECHO]** `_preflop_spot()` para un rival sin acciones devuelve `('no_raise', 'open')`; para un fold devuelve también `('no_raise', 'open')`. En postflop solo importan rivales activos, pero la heurística no distingue “no actuó” de “fold” si se consulta fuera de contexto.

### 3.9 Síntesis preflop

**Hechos que sostienen un defecto crítico:**

- La codificación `b`/`r` no es consistente y la ruta live no usa el contrato.
- 468 de 7.107 decisiones difieren del plan estricto; 434 son aperturas `b` leídas como `OR`.
- 1.080 de 2.329 spots facing open no tienen tabla de call.
- 78 de 147 spots de 4-bet no tienen ninguna tabla.
- La ausencia de tabla se convierte en fold determinista.
- La acción se muestrea, no se elige por frecuencia.
- `SQUEEZE`/`Over_Call` no se usan.

**Clasificación:** defectos críticos de calidad estratégica, no necesariamente bugs de contrato. La convención “ausencia = 0” y la ausencia de `Call_OR` están declaradas; el problema es que el producto las presenta como recomendación, no como límite.

---

## 4. Auditoría de la lógica postflop

### 4.1 Construcción del rango del rival

**[HECHO]** La ruta live:

1. Asigna perfil con `_perfil_for()`: `PEZ` si el stack medio/actual < 50 BB; `TIBURON` en otro caso. Solo hay dos perfiles.
2. Construye el rango con `ProfileRangeModel.prob_vec(perfil, spot, action, pos, villain_pos)`.
3. Aplica `RangeState.set_known_cards(hero + board + blockers)`.
4. Refina con las acciones postflop observadas del rival usando `PostflopRangeModel.prob_vec(perfil, street, facing, board, action)`.

**[HECHO]** No se usa `prob_vec_player()` ni `player_omega()` en la ruta live. El ajuste individual por jugador existe en `player_ranges.py` pero queda para `recommend_loop`, que no es producción. En live, dos rivales distintos con el mismo stack y el mismo perfil reciben exactamente el mismo rango.

**[HECHO]** El modelo preflop por perfil tiene muy poco soporte:

| Perfil / denominador | Observaciones (`opp`) | Celdas no nulas |
|---|---:|---:|
| TIBURON / `no_raise` | 654 | 166 |
| TIBURON / `facing_open` | 312 | 141 |
| TIBURON / `facing_3bet` | 16 | 15 |
| PEZ / `no_raise` | 128 | 84 |
| PEZ / `facing_open` | 55 | 43 |
| PEZ / `facing_3bet` | 5 | 5 |

Para `3bet`, TIBURON tiene 22 observaciones en 11 celdas y PEZ 4 en 3 celdas. Es decir, el rango de 3-bet de cada perfil se estima con un puñado de manos.

### 4.2 El prior plano domina cuando falta la tabla

**[HECHO]** `ProfileRangeModel._prior_grid()` busca, en orden:

1. Tabla simple `PREFIX_POS`.
2. Tabla de par `PREFIX_POS_vs_VILLAIN`.
3. `FLAT_PRIOR = 0.15` con `RuntimeWarning`.

**[HECHO]** En 2.396 jugadores activos con acciones postflop:

| Fuente del prior | Jugadores |
|---|---:|
| Tabla simple exacta | 88 |
| Tabla de par exacta | 427 |
| **`FLAT_PRIOR`** | **1.881 (78,5%)** |
| Total | 2.396 |

**[HECHO]** La fórmula es `(cnt + alpha * prior) / (opp + alpha)` con `alpha = 2.0`. Cuando el prior es plano, se aplica 0,15 a **cada** una de las 1.326 combinaciones; el denominador `opp` es del perfil+denominador, no de la acción. Medido en celdas sin tabla:

| Consulta | Combos no nulos | Combos efectivos (`1/Σw²`) |
|---|---:|---:|
| `TIBURON / facing_open / 3bet / UTG / ''` | 1.326 | 759 |
| `TIBURON / facing_open / call_open / CO / BTN` | 1.326 | 817 |
| `TIBURON / no_raise / limp / BB / ''` | 1.326 | 939 |

Es decir, cuando falta la tabla, el rango no es “la mano del perfil”: es casi uniforme sobre la mayoría de combos. Esto afecta al 78,5% de los villanos activos.

**[HECHO]** Además, la etiqueta que decide qué tabla consultar no coincide con el contrato en la mayoría de los casos. En 2.360 jugadores activos postflop con decisión preflop resuelta, la etiqueta legacy `_preflop_spot` y el contrato estricto coinciden exactamente en 702 (29,7%). Los desacuerdos principales:

| Legacy | Contrato estricto | Jugadores |
|---|---|---:|
| `call_open` | `limp` | 459 |
| `call_open` | `call_limp` | 315 |
| `limp` | `bb_check` | 313 |
| `3bet` | `open` | 281 |
| `3bet` | `rol` | 170 |
| `call_open` | `open` | 41 |
| `call_open` | `call_3bet` | 14 |

No todos los desacuerdos cambian la tabla, pero muchos sí: un `3bet` que en realidad fue apertura consulta `3B` o cae en `FLAT_PRIOR`; un `call_open` que en realidad fue limp consulta `Call_OR` o cae en `FLAT_PRIOR`.

### 4.3 Equity en flop/turn: estática, no de showdown

**[HECHO]** `situation.equity_vs_range()` evalúa la fuerza actual de hero y de cada combo rival con `evaluate_batch`/`evaluate_hand` sobre las cartas disponibles en el board actual. No reparte turn/river. En river es correcta; en flop/turn no es la equity de showdown.

**[HECHO] Ejemplo medido contra rango uniforme (200 runouts, 200 combos):**

| Mano del hero | Board | Equity estática | Equity con runout | Δ |
|---|---|---:|---:|---:|
| `AhKh` (proyecto de color) | `Qh7h2c` | 0,596 | 0,726 | +0,130 |
| `AsAd` (overpair) | `Qh7h2c` | 0,966 | 0,856 | −0,110 |
| `9s8s` (gutshot) | `Qh7h2c` | 0,182 | 0,305 | +0,123 |

**[HECHO]** Esa `sit.equity` se usa en:

- El panel que ve el usuario.
- `range_adv(sit.equity)` para clasificar `HERO`/`NEUTRAL`/`VILLAIN` (`hand_state.range_advantage`, umbral 0,55/0,45).
- Filtros de `rules.plan()` que dependen de `range_advantage` (por ejemplo, c-bet en board WET).

**[HECHO]** `compute_evs()` sí usa `_showdown_equity_by_combo()` cuando `runout=True`; por eso el EV de las acciones puede valorar draws mejor que el panel. Pero:

- `check` se calcula como `equity × pot`, sin apuestas futuras.
- Cada apuesta modela **una sola** respuesta del rival; no hay árbol de calles futuras en live (`tree=False`).
- La equity del panel y la de las reglas no son la misma que la del EV.
- `n_runouts=100` no significa 100 runouts por combo: con un rango completo el muestreo produce del orden de 16 runouts por combo. El parámetro debe leerse como tamaño de muestra, no como garantía por combo.

### 4.4 Modelo de respuesta Oracle

**[HECHO]** `behavior.json` tiene 877 manos, 8.742 observaciones y 143 celdas (111 granular + 32 por_facing). La distribución de `n`:

- 58 de 143 celdas (40,6%) tienen `n < 20`.
- Mediana: 29.
- Máximo: 1.885.

**[HECHO]** `Oracle.p_action()` usa cuatro niveles: `granular` → `por_facing` → `label` → `poblacion`. En los dos últimos, `returned_n = 0`; `OracleResponse.alpha = min(1, n/20)` y, con `alpha = 0`, usa la heurística pura. `alpha` es un exponente, no una mezcla convexa ni un porcentaje de confianza.

**[HECHO]** En live, el perfil es `PEZ`/`TIBURON` por stack; no se usa la identidad del jugador para el Oracle. El ajuste individual `omega` no se aplica. El modelo de respuesta es, por tanto, poblacional y con soporte desigual.

### 4.5 Modelo de rangos postflop

**[HECHO]** `PostflopRangeModel`:

- 5 buckets de fuerza por percentiles del board.
- `alpha = 2.0`.
- 866 manos usadas de 877 fiables.
- 116 celdas `opp` y 197 celdas `cnt`.
- `P(A|H,bucket) = (cnt + alpha * prior) / (opp + alpha)`.
- `prob_vec()` asigna a cada combo la probabilidad de su bucket.
- El prior es el Oracle; si el Oracle no está inyectado (por ejemplo, `load()`), usa un prior plano 0.2.

**[HECHO]** `build_models()` construye el Oracle desde las mismas manos y lo inyecta en `postflop_model._oracle`; `PostflopRangeModel.load()` no lo restaura. La ruta live usa `build_models()`, así que tiene Oracle; la ruta de carga standalone no.

**[HECHO]** El modelo postflop no tiene dimensión multiway: `facing` describe el contexto de apuesta (`none`, `cbet`, `donk`, `barrel`, `raise`), no el número de rivales. Los buckets y las celdas se estiman con la misma distribución para HU y MW.

### 4.6 Reglas y ventajas

**[HECHO]** `rules.plan()` recibe `n_players`, pero solo lo usa para:

- `multiway = n_players > 2`.
- `multiway_soportado` (siempre `False` en MW).
- `_multi_sizes`: umbral mínimo de sizing (0,33 en 3-way; 0,50 en 4-way+).
- Filtros que convierten el spot en check con manos débiles (`§4`).

**[HECHO]** `nut_advantage` se calcula con la mano del hero (`hand_state.HandState.nut_advantage()`): `HERO` si la fuerza es strong made, `VILLAIN` si es high card sin draw, `NEUTRAL` en el resto. Se pasa a `rules.plan()` pero **ninguna regla lo consulta** (TODO F5 en `rules.py:307`).

**[HECHO]** `range_advantage` se calcula con la equity estática (`range_advantage(hero_equity)`). Por tanto, en flop/turn la ventaja de rango que usan las reglas hereda el sesgo de la equity estática.

### 4.7 Síntesis postflop

**Hechos que sostienen defectos críticos:**

- La equity del panel/reglas en flop/turn no es de showdown; el error medido llega a 13 puntos porcentuales.
- El 78,5% de los villanos activos no tiene prior posicional; en acciones sin tabla el rango se vuelve casi uniforme (759–949 combos efectivos).
- La etiqueta preflop que elige la tabla coincide con el contrato solo en el 29,7% de los jugadores activos postflop.
- El soporte por perfil es escaso (3-bet: 22 observaciones TIBURON, 4 PEZ).
- El Oracle usa heurística pura con `n=0`; el 40,6% de las celdas tiene `n<20`.
- La respuesta del rival modela una sola acción y no hay árbol futuro en live.
- `nut_advantage` no se usa; `range_advantage` es estático.

---

## 5. Mapa de rutas live y divergencias

### 5.1 Ruta real de producción

**[HECHO]** `Asistente.recomendaciones()` recorre los héroes conocidos y llama `_recomendacion_para()` para cada uno. En postflop:

1. `villain = self._villain_id(...)`: elige **un** rival.
   - Si la apuesta mayor de un rival supera la del hero, elige a ese rival.
   - Si no, elige al activo con mayor stack.
2. `perfil = self._perfil_for(villain, state)`: PEZ si la media histórica (o el stack actual si no hay historial) está por debajo de 50 BB; sin datos, TIBURON.
3. `spot, action = _preflop_spot(hand, villain_pos)`.
4. `reach = range_model.prob_vec(perfil, spot, action, pos=villain_pos, ...)`.
5. Refina con las acciones postflop del **mismo** rival.
6. `sit = situation(hero, board, villain_reach=rs, ...)`.
7. `n_players` se cuenta desde el estado OCR y solo alimenta `rules.plan()`.
8. `compute_evs()` y `select_best()`.

**[HECHO]** En multiway, los rivales que no son `villain` no entran en la equity ni en la respuesta. Solo sus cartas conocidas entran como blockers. Si no se conocen, son invisibles para el cálculo.

### 5.2 Cuánto pesa el multiway

**[HECHO]** `multiway.metrica_politica()`:

| Base | Decisiones no-fold del hero | Multiway | Porcentaje | Techo | Desconocidos |
|---|---:|---:|---:|---:|---:|
| Todas (1.344 manos) | 894 | 399 | 44,6% | 423 | 24 |
| Fiables (877 manos) | 506 | 210 | 41,5% | 234 | 24 |

El denominador excluye folds del hero; el techo suma los casos `DESCONOCIDO` que podrían ser MW. La base fiable es la que alimenta los modelos; la base total es la que se parece más a lo que ve el live.

### 5.3 Jerarquía y sombra

**[HECHO]** `hierarchy.classify_villains()` y `shadow_record()` registran:

- `main`, `aggressors`, `checkers`, `callers`, `pending`.
- `equity_main` contra el rango del rival principal.
- `multiway`, `multiway_soportado`, `multiway_motivo`, `politica_multiway`, `n_players`.

**[HECHO]** La sombra no modifica `evs`, `rp` ni `select_best`; por construcción, la acción no cambia. Sirve para medir, no para decidir.

### 5.4 Divergencias entre rutas

| Aspecto | `asistente_live` (producción) | `recommend_loop` (demo/análisis) | `preflop_contract` (sombra) |
|---|---|---|---|
| Preflop spot | `_preflop_spot` / `_preflop_raises` (legacy) | parámetros `villain_spot`/`villain_action` | `first_decision` / `table_plan` |
| Rango rival | `prob_vec(perfil, ...)`; no `omega` | `prob_vec_player(player, ...)`; sí `omega` | no construye rango |
| Multiway | un solo villano | `union()` de rangos (prohibido) | no aplica |
| Equity | estática en flop/turn | `compute_evs` con runout opcional | no aplica |
| Acción | `rules.select_best` | `select_best` | no decide |
| Uso | producción | demo/tests | sombra |

**[HIPÓTESIS]** La diferencia de `prob_vec_player` vs `prob_vec` puede explicar parte de la brecha entre lo que se valida en tests/demo y lo que se recomienda en live. Debe medirse con un replay de las mismas manos por ambas rutas.

**[HIPÓTESIS]** `n_players` se cuenta con `state` (OCR) y no con `_recorded_folds()`. Si el OCR tarda en apagar la estrella de un jugador folded, el live puede contar un rival de más, marcar MW y cambiar sizes. No se ha medido; requiere un replay con estados reales.

---

## 6. Diseño de arquitectura Multiway validable

### 6.1 Principios

1. **No usar `RangeState.union()`** como distribución conjunta. Sumar masas no normaliza y, aunque se normalice, pierde la identidad de cada villano y no permite respuestas independientes.
2. **No promediar equities HU.** La equity de campo no es `(1/N) Σ equity_hero_vs_villano_i`. Hay que exigir que el hero gane a **todos** los rivales (con ties repartidos) sobre una distribución conjunta.
3. **Distribución conjunta con card removal.** Para villanos `1..N`, con rangos `r_i(h_i)`:
   ```
   p(h_1, ..., h_N) ∝ Π_i r_i(h_i) · 1[cartas disjuntas entre sí, hero y board]
   ```
   normalizada. Si hay acciones observadas, `r_i` se sustituye por la posterior `r_i | acciones`.
4. **Respuestas por villano, no una respuesta agregada.** Cada villano tiene su `P(fold/call/raise | h_i, amount, pot, contexto)`. El orden de acción y los side pots se resuelven con el estado real.
5. **Trazabilidad y confianza.** Cada rango y cada equity debe llevar procedencia, cobertura, tamaño de muestra/ESS y una etiqueta de confianza. Si no hay evidencia suficiente, se devuelve “no soportado”, no un número inventado.
6. **Ningún cambio de recomendación en sombra.** La primera fase MW solo mide y registra; no altera `evs`, `rp` ni `select_best`.

### 6.2 Componentes propuestos

**a) `FieldState`**

- `hero_codes`, `board_codes`, `street`, `pot`, `to_call`.
- `players`: orden de acción, posición, stack, bet, `folded`, `allin`, cartas conocidas.
- `history`: acciones por calle con instante y orden.
- Invariantes: sin cartas duplicadas; `pot` y `stacks` no negativos; `allin` consistente con `multiway.posiciones_allin`; `no_puede_actuar_en_instante` para elegibilidad.

**b) `VillainBelief` (uno por villano)**

- `RangeState` individual, no unión.
- `spot`, `action`, `source`, `prior_source`, `coverage`, `confidence`.
- `blockers` aplicados individualmente.
- Historial de actualizaciones postflop.

**c) `JointSampler`**

- Muestreo secuencial con rechazo o importance sampling:
  - Muestrear `h_1 ~ r_1`.
  - Muestrear `h_2 ~ r_2` condicionado a no chocar con `h_1`, hero y board.
  - Repetir para `N` villanos.
- Devolver `K` tuplas compatibles con pesos; calcular `ESS = (Σw)² / Σw²`.
- Semilla determinista y registro del `ESS`.
- Si `ESS` cae por debajo de un umbral, degradar a “no soportado” o aumentar `K`; nunca sustituir por HU.

**d) `FieldEquity`**

Para cada tupla conjunta, evaluar la mano del hero y la de cada villano en el board final (con runout si faltan cartas):

```
gana   = 1 si hero > todos los villanos
empata = 0.5 si hero >= todos y al menos uno empata
pierde = 1 - gana - empata
equity_campo = Σ_tupla w · (gana + empata)
```

No es la media de equities por rival. Un contraste útil para tests: con dos rivales independientes y idénticos, la equity de campo es aproximadamente `e²` (más términos de tie), no `e`.

**e) `FieldResponse`**

- Para cada villano y cada tupla, `P(fold/call/raise | h_i, amount, pot, perfil, posición, historial)`.
- Resolver la secuencia de respuestas en el orden real; actualizar pot, stacks, all-in y side pots.
- No usar una respuesta agregada del pool.
- Si un villano no puede actuar (`no_puede_actuar_en_instante`), no responde.

**f) `MultiwayActionEV`**

- Para cada candidata del hero, integrar sobre tuplas conjuntas y respuestas de los villanos.
- Empezar con una calle (sin árbol futuro) y comparar contra el `compute_evs` HU en el límite de un villano.
- Después, una calle futura con abstracción y número limitado de nodos.
- Side pots: capas de pot por contribución; elegibilidad por all-in; nunca pagar a un villano que no puede ganar una capa.

### 6.3 Fases de implementación

| Fase | Qué hace | Cambia acción | Criterio de salida |
|---|---|---|---|
| MW-0 | Sampler conjunto + `FieldEquity` en sombra; log de ESS, cobertura y diferencia vs HU | No | Invariantes y reducción a HU pasan |
| MW-1 | Panel muestra equity de campo y confianza; recomendación sigue HU marcada “no soportado” | No | Validación de calibración y cobertura |
| MW-2 | EV de una calle con respuestas independientes; solo acciones con ESS suficiente | Sí, con gate | Aceptación de EV y regresión |
| MW-3 | Árbol multi-calle con abstracción; activación limitada | Sí, con gate | Validación contra exacto y contra HU |
| MW-4 | Activación general y `MULTIWAY_SOPORTADO=True` | Sí | Contrato nuevo firmado y auditoría independiente |

**【PROPUESTA】** No se debe cambiar `MULTIWAY_SOPORTADO` hasta MW-4. Las fases MW-1/MW-2 pueden mostrarse como información, pero la recomendación debe seguir declarando el límite.

### 6.4 Qué no hacer

- No usar `RangeState.union()` para “combinar” villanos.
- No normalizar la unión y llamarla “distribución conjunta”.
- No calcular `equity` como media de equities HU.
- No usar el rango del villano principal como proxy del campo.
- No rellenar tablas ausentes con 0 ni con 0,15 y presentarlo como recomendación.
- No activar MW con datos cuya procedencia no esté certificada.

---

## 7. Dependencias y riesgos

| Dependencia / riesgo | Estado | Impacto | Mitigación |
|---|---|---|---|
| F0 D1 | `PARTIAL`; reauditoría pendiente | Alto: cualquier escritura/derivado no es certificable | No escribir datos; usar solo lectura; cerrar D1 antes de F1/F2 |
| Bypasses de F0 con subclases de primitivos | Reportados por reauditoría previa; no revalidados aquí | Alto: evidencia CAS/hash podría falsificarse | Reauditoría independiente; no confiar en derivados |
| Artefactos `arbol_sucio:true` / commit `0fcceed` | Declarado en JSON | Alto: no reproducibles desde HEAD | Reconstruir y comparar; no usar como ground truth |
| Base fiable 877/1.344 | 65,3% | Alto: sesgo de selección | Reportar siempre denominador; validar con la base total en sombra |
| Tablas preflop con 30 huecos | 1.080 spots sin call | Crítico estratégico | Declarar “sin tabla” y no recomendar; o recolectar datos |
| Modelos de 2 perfiles | PEZ/TIBURON por stack | Alto: no hay adaptación individual en live | Usar `omega` con validación; o modelos por jugador con shrinkage |
| Muestras pequeñas (3bet 22/4) | Medido | Alto: intervalos amplios | Shrinkage, intervalos, fallback explícito |
| Equity estática en flop/turn | Medido | Crítico: reglas y panel sesgados | Usar `runout_equity` en panel/reglas o declarar “equity actual” |
| Sin árbol futuro en live | `tree=False` | Alto: EV de check/bet no comparables | Árbol abstracto o declarar MVP1 |
| OCR y orden de acciones | No medido | Medio/alto: `n_players`, `to_call`, `facing` | Replay con estados; invariantes; tests de orden |
| Leakage en `decisions.jsonl`/`observations.json` | No auditado | Alto para validación | Split por mano/tiempo; auditar pre-decisión |
| Rendimiento de samplers | Por medir | Medio: latencia | Vectorización, ESS, presupuesto por decisión |
| Confianza del usuario | Panel actual muestra equity HU en MW | Alto: falsa sensación de precisión | Etiqueta “no soportado” visible; confianza explícita |

---

## 8. Plan priorizado

### 8.1 Clasificación de defectos

| # | Defecto / límite | Clasificación | Evidencia | Acción propuesta | Complejidad |
|---|---|---|---|---|---|
| 1 | F0 D1 `PARTIAL`; artefactos sucios | **Bloqueante** | Doc F0; meta JSON | Cerrar D1 y reconstruir artefactos antes de certificar | M |
| 2 | MW sin equity conjunta; 41,5–44,6% de decisiones | **Bloqueante para MW** | `metrica_politica`; `_recomendacion_para` | Mantener `MULTIWAY_SOPORTADO=False`; MW-0 en sombra | L |
| 3 | Preflop `b`/`r` y ruta legacy vs contrato | **Crítico** | 468/7.107; 434 `b`→OR | Usar `table_plan`/contrato en live; tests de regresión | S–M |
| 4 | 1.080/2.329 facing open sin `Call_OR` | **Crítico** | Cobertura estricta | Declarar “sin tabla” y no recomendar; o datos | M–L |
| 5 | 78,5% sin prior posicional; rango casi uniforme | **Crítico** | `ProfileRangeModel`; effective combos | Prior por posición/par; fallback explícito; no 0,15 | M–L |
| 6 | Equity estática en flop/turn | **Crítico** | Δ 13 pp | Panel/reglas con runout; separar “equity actual” y “showdown” | M |
| 7 | Etiqueta preflop del rango postflop inestable | **Crítico** | 29,7% match | Una sola lectura (contrato) y posterior por acciones | M |
| 8 | Oracle con 40,6% celdas `n<20`; heurística con `n=0` | **Crítico** | `behavior.json` | Shrinkage/intervalos; no presentar como probabilidad calibrada | M |
| 9 | Sin árbol futuro; una sola respuesta | **Importante** | `tree=False`; MVP1 | Árbol abstracto o etiqueta de límite | L |
| 10 | `nut_advantage` no se usa; `range_advantage` estático | **Importante** | `rules.py:307`; `hand_state.py:177` | Definir ventaja vs campo; usar o eliminar | M |
| 11 | `SQUEEZE`/`Over_Call` no usados | **Importante** | `_recom_preflop` | Implementar spot o declarar no soportado | M |
| 12 | Muestreo preflop en vez de argmax | **Importante** | `_sample_preflop_action` | Decidir producto: mixta vs determinista; test | S |
| 13 | `_pf_evs` reescala frecuencias independientes | **Importante** | `_pf_evs` | Validar contra observado; documentar | S |
| 14 | `omega` no se usa en live | **Mejora** | `prob_vec` vs `prob_vec_player` | Activar con shrinkage y validación | M |
| 15 | Sizings limitados; sin overbet | **Mejora** | `rules.py` | Añadir sizings con evidencia | M |
| 16 | OCR `n_players`/orden | **Mejora / hipótesis** | No medido | Replay y tests de estado | M |

### 8.2 Secuencia recomendada

**Etapa A — Contención (sin cambios de recomendación)**

1. Mantener `MULTIWAY_SOPORTADO=False`.
2. No escribir datos ni artefactos; no `--apply`.
3. Congelar una copia de los datos/artefactos actuales con hashes para comparar.
4. Reauditar F0 D1 y la procedencia de los artefactos.
5. Añadir telemetría de cobertura: cada consulta preflop/postflop debe registrar `status` (`exact`, `fallback`, `missing`), `source` y `confidence`.

**Etapa B — Corregir HU antes de MW**

1. Unificar la lectura preflop en `preflop_contract` (producción y entrenamiento) y medir el impacto con replay.
2. Resolver la semántica `b`/`r` con una prueba de datos, no con una heurística.
3. Cambiar “tabla ausente → fold” por “sin tabla → no recomendación / confianza baja” (contrato nuevo).
4. Completar o declarar la ausencia de `Call_OR` para MP/CO/SB.
5. Llevar runout/equity de showdown al panel y a `range_advantage`; separar “equity actual” de “equity de showdown”.
6. Reconstruir `ProfileRangeModel`/`PostflopRangeModel` con el contrato y con `omega` individual si se valida.
7. Medir calibración del Oracle y de los rangos con split por mano/tiempo.

**Etapa C — MW en sombra**

1. Implementar `JointSampler` y `FieldEquity` sin tocar la acción.
2. Registrar ESS, cobertura y diferencia contra HU.
3. Validar con casos sintéticos exactos y reducción a HU.
4. Solo entonces abrir MW-1/MW-2 con gates.

**Etapa D — Activación**

1. Firmar un contrato nuevo de MW (no editar `CONTRATO_F72A.md` a escondidas).
2. Auditoría independiente de F0 y de la validación MW.
3. Cambiar `MULTIWAY_SOPORTADO` en un único sitio y con test que lo fije.

---

## 9. Plan de validación y criterios de aceptación

### 9.1 Principios de validación

- **Sin leakage:** usar solo estado pre-decisión. No usar acciones futuras, cartas de rivales no reveladas ni resultados.
- **Split por mano/tiempo:** nunca partir por observación suelta; una mano no puede estar en train y test.
- **Denominadores explícitos:** reportar manos, decisiones, celdas, `n`, cobertura y ESS.
- **Reproducibilidad:** semillas fijas, versiones de código/datos y hashes.
- **Comparación contra baseline:** HU actual, reglas actuales, y oráculo exacto cuando exista.

### 9.2 Matriz de validación

| Validación | Método | Criterio de aceptación |
|---|---|---|
| Paridad HU | Comparar `FieldEquity` con `compute_evs`/`equity_vs_range` cuando `N=1` | Diferencia ≤ 0,002 en equity; misma acción en ≥ 99% de spots |
| Exactitud sintética MW | 2–3 villanos, rangos pequeños, board de 3 cartas; enumeración exacta vs sampler | Error absoluto ≤ 0,005; ESS ≥ umbral |
| Card removal | Verificar que ninguna tupla comparte cartas con hero/board/otros | 0 violaciones en 10⁵ muestras |
| Normalización | `Σ p = 1`; rangos vacíos se declaran | 0 sumas inválidas; 0 “unión” |
| Side pots | Casos sintéticos con all-in de distintos stacks | Pagos correctos; nadie gana capas no elegibles |
| Preflop coverage | Replay de 7.107 decisiones | 0 recomendaciones con `status=missing`; 100% con `status` registrado |
| Preflop classification | Legacy vs contrato | 0 diferencias no explicadas; las diferencias se reportan por causa |
| Calibración Oracle | Brier/log-loss en holdout por mano | Mejor o igual que baseline; intervalos/cobertura reportados |
| Calibración de rangos | Frecuencia observada vs predicha por bucket | Sin celdas `n<20` presentadas como calibradas |
| Equity de showdown | Flop/turn vs enumeración exacta en casos pequeños | Error ≤ 0,005 |
| MW sombra | Replay sin cambio de acción | 0 cambios de `evs`/acción; log completo |
| Acción MW | Comparar con baseline HU y con expertos/reglas | No degradar EV estimado; revisar discrepancias |
| Rendimiento | Latencia p95 por decisión | Dentro del presupuesto acordado; ESS suficiente |
| Regresión | Suite completa + tests nuevos | 0 fallos; tests de contrato actualizados solo con contrato nuevo |

### 9.3 Criterios de aceptación para activar MW

**[PROPUESTA]** No activar `MULTIWAY_SOPORTADO=True` hasta que se cumplan **todos**:

1. F0 D1 cerrado y artefactos reconstruidos desde HEAD con árbol limpio.
2. `FieldEquity` reducido a HU coincide con el motor HU dentro de tolerancia.
3. Casos sintéticos exactos pasan (error ≤ 0,005; card removal; side pots).
4. En sombra, la equity de campo tiene cobertura y ESS reportados; no hay recomendaciones sin confianza.
5. La validación de calibración muestra que el modelo no está peor que el baseline HU en losspots medidos.
6. Un contrato nuevo de MW firmado, con `MULTIWAY_SOPORTADO` en un único sitio y tests que lo fijen.
7. La UI muestra “equity de campo” y “confianza” sin mezclarla con la equity HU.

### 9.4 Entregables de la siguiente fase

- `DOCS/AUDITORIA_ESTRATEGICA_MULTIWAY_2026-11-13.md` (este informe).
- Un conjunto de mediciones reproducible (script read-only) que genere las tablas de las secciones 3, 4 y 5.
- Un `JointSampler`/`FieldEquity` en sombra, sin cambios de acción, con tests sintéticos.
- Un replay de las 1.344 manos que compare legacy vs contrato y HU vs campo, con denominadores explícitos.
- Un informe de calibración con intervalos y cobertura, no solo un número puntual.

---

## Apéndice A. Método de medición

**[HECHO]** Las cifras se obtuvieron con scripts Python read-only sobre el repo, sin modificar archivos:

- `motor.learn.load_hands()` y `load_hands(reliable_only=True)`.
- `motor.multiway.metrica_politica()`.
- `motor.preflop.audit_engine_coverage()` y `load_tables()`.
- `motor.asistente_live._preflop_spot`, `_preflop_raises`, `_pf_table_lookup`.
- `motor.preflop_contract.table_plan`, `first_decision`.
- `motor.player_ranges.ProfileRangeModel.load()`, `p_matrix`.
- `motor.situation.equity_vs_range` y `motor.decision.runout_equity`.
- Lectura directa de `data/behavior.json`, `postflop_ranges.json`, `profile_ranges.json`.

**No se ejecutó la suite de tests completa.** Las cifras no sustituyen a una validación; son evidencia de auditoría.

## Apéndice B. Invariantes que no deben romperse

1. `MULTIWAY_SOPORTADO` sigue en `False` hasta contrato nuevo.
2. `RangeState.union()` no se usa como distribución conjunta.
3. La equity MW no es la media de equities HU.
4. Ninguna tabla ausente se convierte en fold sin declararlo.
5. Ningún rango sin evidencia se presenta como calibrado.
6. Ningún cambio de acción en sombra.
7. Ninguna escritura en `data/` sin F0/F1/F2 y autorización explícita.
8. Toda decisión registra `status`, `source`, `coverage` y `confidence`.

---

**Fin del informe.** No se ha modificado ningún archivo de datos, modelo, manifiesto o pin. No se ha hecho commit ni staging. `MULTIWAY_SOPORTADO` permanece en `False`.
