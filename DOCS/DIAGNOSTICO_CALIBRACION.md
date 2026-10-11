# Diagnóstico — Mecanismos de Calibración

Estado actual de los mecanismos que convierten datos observados en probabilidades
dentro del motor. Documento descriptivo: inventaría lo que existe, cómo está
cableado, con qué constantes y con qué cobertura real. No propone implementación.

Medido contra `data/hands_db.jsonl` en el commit actual (1280 manos).

---

## 1. Veredicto

El sistema **sí tiene** mecanismos de calibración, y son cinco. Todos comparten
la misma familia estadística: **encogimiento (*shrinkage*) hacia un prior** con
pseudo-conteos, más un ajuste individual por jugador.

Pero el diagnóstico tiene un matiz que condiciona cualquier trabajo posterior:

| | |
|---|---|
| Mecanismos de calibración implementados | 5 |
| Mecanismos conectados a producción | 3 de 5 |
| Función de calibración que escriba `BASE_WEIGHT_MAP` / `_ACTION_PROBS` | **0** |
| Artefactos derivados al día respecto a la DB | **0 de 5** |

Dos consecuencias:

1. **La taxonomía → peso → probabilidad no está cableada.** `BASE_WEIGHT_MAP` y
   `_ACTION_PROBS` se calculan y se verifican en tests, pero ninguna ruta de
   producción los lee. El prior real del sistema viene de otro sitio.
2. **Los artefactos derivados están todos desfasados.** Declaran 327–339 manos
   cuando la base tiene 1280. El sistema está operando sobre ~26% de los datos
   disponibles.

---

## 2. Mapa de cableado

Lo que realmente se ejecuta en `recommend_loop._build_villain_range` (`recommend_loop.py:71-85`):

```
_build_villain_range()
│
├─ range_model + villain_playerknown
│   └─ prob_vec_player()          player_ranges.py:254
│       └─ p_player()             player_ranges.py:242
│           ├─ p_matrix()        player_ranges.py:174   ← M1: encogimiento a prior
│           │   ├─ cnt/opp       desde hands_db.jsonl
│           │   └─ _prior_grid() player_ranges.py:157   ← lee preflop_matrices.json
│           └─ player_omega()    player_ranges.py:208   ← M4: ajuste individual
│
└─ sin perfil
    └─ opening_range(pos)         preflop.py:97          ← prior puro, sin datos

compute_evs()                      decision.py
└─ OracleResponse()               decision.py:82        ← M3: funde M2 con heurística
```

`BASE_WEIGHT_MAP` y `_ACTION_PROBS` **no aparecen en este grafo.**

---

## 3. Inventario de mecanismos

### M1 — ProfileRangeModel (preflop, mano conocida)

**Es el mecanismo principal. Es el único que consume `hands_db.jsonl` para
producir probabilidades por mano.**

| | |
|---|---|
| Archivo | `motor/player_ranges.py` |
| Fórmula | `P(A\|H,C,P) = (cnt + alpha·prior) / (opp + alpha)` (`:184`) |
| `alpha` | `DEFAULT_ALPHA = 2.0` pseudo-conteos (`:61`) |
| `prior` | Tabla 13×13 de `data/preflop_matrices.json` (`:157-172`) |
| `prior` alternativo | `FLAT_PRIOR = 0.15` si la acción no tiene tabla (`:62`, `:160`, `:171`) |
| Granularidad | Celdas 13×13 del grid de ranks, proyectadas a 1326 combos (`:191-195`) |
| Ajuste individual | `omega` clamp `[0.25, 4.0]`, fade-in `min(1, n/20)` (`:238-240`) |

Agrupamiento de conteos:

```
opp[(perfil, denom)]                          ← todas las 1as decisiones con mano
cnt[(perfil, denom, categoría)]               ← una entrada por acción
denom ∈ {no_raise, facing_open, facing_3bet}
categoría ∈ 13 (open, limp, rol, call_limp, call_open, 3bet,
                squeeze, 4bet, call_3bet, fold, fold_vs_open,
                fold_vs_3bet, bb_check)
```

**Limitaciones documentadas en el propio código:**

- **La posición no desglosa los conteos** (`player_ranges.py:39-42`). Las claves son
  `(perfil, denom)`; `pos` solo modula *qué prior* se elige (`:163-169`), nunca los
  contadores. Es decir, `P(A|H, BTN)` y `P(A|H, UTG)` comparten el mismo `cnt`.
- **Acción sin tabla cae a prior plano.** `CAT_TABLE` (`:65-69`) mapea 9 de las 13
  categorías. Las 4 restantes — `fold`, `fold_vs_open`, `fold_vs_3bet`,
  `bb_check` — no tienen prefijo, luego usan `FLAT_PRIOR = 0.15` plano y
  uniforme en las 169 celdas. **El fold no está modelado en absoluto**: solo
  hereda un 15% constante.
- **El prior no distingue `hero` de rivales.** `HERO_NAMES = ('Jarduan',)` se
  etiqueta con su propio perfil (`player_ranges.py:44-46`).

### M2 — Oracle / behavior.py (postflop, P(A|C))

**Es el único mecanismobayesiano con posterior explícita. No toca las manos.**

| | |
|---|---|
| Archivo | `motor/behavior.py`, clase `Oracle` (`:71`) |
| Dimensión | `(perfil, street, facing, texture)` → `{x,b,c,f,r}` |
| Persistencia | `data/behavior.json` |
| Perfiles | 2: `PEZ` y `TIBURON` (`:163-170` de `profile.py`) |

Fallbacks escalonados por nivel de evidencia (`:127-134`):

| Nivel | Clave | Fuente |
|---|---|---|
| 1 | `(label, street, texture, facing)` | `granular` |
| 2 | `(label, street, facing)` | `por_facing` |
| 3 | `(label, street)` | agregado de `por_facing` |
| 4 | población | agregado de todas las etiquetas |

**Cobertura real del artefacto actual:**

| Métrica | Valor |
|---|---|
| Manos declaradas | 339 |
| Observaciones declaradas | 3474 |
| Celdas `granular` | 81 |
| Celdas `por_facing` | 27 |
| `n` en `granular` | mín 3, mediana 13, máx 708 |
| `n` en `por_facing` | mín 4, mediana 57, máx 708 |

Con mediana 13 por celda granular, la granularidad de nivel 1 descansa sobre
muestras pequeñas; el fallback a nivel 2 es el régimen real de operación.

### M3 — OracleResponse (fundido con la heurística)

| | |
|---|---|
| Archivo | `motor/decision.py`, clase `OracleResponse` (`:82`) |
| Entrada | distribución de M2 + `default_response()` |
| Fade-in | `alpha = min(1.0, n/20)` (`:106`) |
| Reestilamiento | `scale = (3.0 · profile)^alpha` (`:125`) |

Convierte el perfil en un multiplicador sobre la respuesta heurística de
equidad, y renormaliza (`:127`). Es el punto donde el perfil postflop efectivamente
toca el cálculo de EV.

Observación: el perfil se recorta a `[0.05, 0.90]` (`:124`) y se eleva a la
`alpha`. Con `n = 708` la mezcla es total; con `n = 3` es prácticamente
heurística pura.

### M4 — PlayerProfile (posterior Beta + ω)

**Único mecanismo con posterior probabilística real. Trabaja sobre estadísticas
agregadas, no sobre manos.**

| | |
|---|---|
| Archivo | `motor/profile.py` |
| Media posterior | `mean = (act + 1) / (opp + 2)` (`:150`) — Beta(1,1) |
| Confianza | media geométrica de las masas modales (`:157-161`) |
| `omega` | `clamp(freq_real / base_rate, 0.25, 4.0)` (`:179-192`) |
| `base_rate` | media ponderada de `preflop_matrices.json` (`:281-304`) |

El prefijo de la tabla determina el stat usado (`_stat_for_table`): `OR_`→`pfr`,
`3B_`→`b3`, etc.

### M5 — postflop_ranges (encogimiento por buckets de fuerza)

| | |
|---|---|
| Archivo | `motor/postflop_ranges.py` |
| Fórmula | `(cnt + alpha·prior) / (opp + alpha)` (`:203`) |
| `alpha` | `DEFAULT_ALPHA = 2.0` (`:53`) — idéntico a M1 |
| Clave | `(perfil, street, facing, bucket)` (`:191`) |
| `prior` | P(A\|C) del Oracle (M2), si no: `{a: 0.2}` plano (`:196`) |

A diferencia de M1, aquí la condición es la **fuerza de la mano** discretizada en
`n_buckets`, no el rango. Es el mecanismo correcto conceptualmente: sí depende de H.

### Desconectadas — `BASE_WEIGHT_MAP` y `_ACTION_PROBS`

| | |
|---|---|
| Ubicación | `motor/ranges.py:85-133` y `:492-539` |
| Consumidores | `default_action_prob` (`:586`) ← solo `test_ranges.py` |
| Entran al `reach` | Nunca, en ningún punto de producción |
| Función que los escriba | No existe |

`_BASE_WEIGHT` se calcula para los 1326 combos y alimenta `base_weight()`,
`class_weights_vector()` y `class_weights_for_reach()` — esta última
(`:366-369`) multiplica `reach` por `_BASE_WEIGHT`, pero **no se invoca desde
ningún sitio**.

**Anomalía semántica detectada:** en las 38 sub-clases de `_ACTION_PROBS`,
`b >= r` sin excepción, y `'b'` es la clave máxima solo en las 6 sub-clases más
fuertes; en 18 la máxima es `'f'` y en 14 es `'c'`. La clave `'r'` **nunca** es la
máxima. Esto sugiere que `'r'` y `'b'` no distinguen lo que su nombre sugiere, lo
que importa si se van a recalibrar desde datos.

---

## 4. Estado de los datos

### Base cruda

| | |
|---|---|
| Ruta | `data/hands_db.jsonl` |
| Manos | 1280 |
| Jugadores distintos | 181 |
| Posiciones | 6 (`UTG, MP, CO, BTN, SB, BB`) |

### Desfase de los artefactos derivados

| Artefacto | Declara | Real | Antigüedad |
|---|---|---|---|
| `preflop_stats.json` | 327 manos | 1280 | 26% |
| `behavior.json` (M2) | 339 manos, 3474 obs | 1280, **13715 obs** | 25% de las observaciones |
| `observations.json` | 3373 obs | **13715 obs** | 25% |
| `db_health.json` | `ts` 2026-08-09 | — | anterior a la corrección |
| `profile_ranges.json` (M1) | sin `hands` verificable | 1280 | no auditable |

`observations.json` debería pasar de 3373 a 13715 filas: **falta ~75% de las
observaciones**.

### `preflop_matrices.json` — el prior, y su problema de origen

117 tablas de 13×13, todas de producción manual.

| Por acción | n | | Por posición | n |
|---|---|---|---|---|
| `3B`, `5B`, `4B`, `Call_3B`, `Call_4B`, `Call_5B` | 15 c/u | | BB | 27 |
| `Call_OR` | 8 | | BTN, SB | 20 c/u |
| `SQUEEZE` | 6 | | MP, CO | 17 c/u |
| `OR`, `ROL` | 5 c/u | | UTG | 16 |
| `Over_Call` | 3 | | | |

**No existe `OR_BB`.** `opening_range('BB')` (`preflop.py:97`) no tiene tabla de
open para la BB y cae al comportamiento de fallback. Es el hueco más visible del
prior, y BB es la posición con más decisiones en la muestra.

Ningún código del repo escribe este archivo. Es el eslabón que convierte datos en
probabilidad **y está desconectado de los datos**.

---

## 5. Calidad de los datos para calibrar

Medido sobre las primeras 900 manos (la ventana corregida declarada):

| | |
|---|---|
| Eventos preflop | 4695 |
| Con mano conocida | 1174 |
| Utilizables (carta válida) | 1172 |
| Sub-clases cubiertas | 35 de 36 |

**Cartas inválidas:** 2, ambas con valor `'-'`, ambas en `H_0350` (índice de línea
347). Trivial, pero `load_hands` no las filtra: `preflop_events` las emite y
`_preflop_category` lanza `ValueError`.

### Escasez

Sobre 140 celdas (sub-clase × acción, mapeo a 4 claves):

| `n` | Celdas | % |
|---|---|---|
| ≤ 0 | 21 | 15% |
| ≤ 5 | 85 | 61% |
| ≤ 10 | 114 | 81% |

Distribución por sub-clase: de 3 (`premium_suited_broadway`) a 404 (`other`).

Con el 61% de las celdas en n≤5, **una calibración por frecuencias crudas sería
ruido**. Los mecanismos existentes ya lo resuelven bien: los tres shrinkage usan
`alpha·prior` comoteo explícito.

### `other` concentra un tercio de la muestra

| Sub-clase | n | % |
|---|---|---|
| `other` | 404 | **34.5%** |
| `weak_offsuit_ace` | 57 | 4.9% |
| `premium_offsuit_ace` | 46 | 3.9% |
| `weak_suited_ace` | 38 | 3.2% |

La clase residual recoge más que la tercera parte de las decisiones con mano
conocida, y es la más poblada con diferencia. Cualquier calibración que la trato
como una categoría más hereda esa concentración: un tercio del modelo quedaría
gobernado por un cajón sin significado de rango.

---

## 6. Lo que no existe

Confirmado por búsqueda sobre todo el repo:

| Ausente | Nota |
|---|---|
| `fit` / `calibrate` / `optimize` | 0 ocurrencias de `.fit()` en todo el código Python |
| Escritura de `BASE_WEIGHT_MAP` | literales en `ranges.py`, solo lectura |
| Escritura de `_ACTION_PROBS` | ídem |
| Escritura de `preflop_matrices.json` | ningún `open(...,'w')` lo apunta |
| Desglose de conteos por posición | ni M1 ni `learn.PreflopStats` indexan por `pos` |
| Resultado en `observations.json` | `extract_hand` descarta `winner`, `showdown`, `final_pot` |
| Dependencias ML | solo `numpy` + `scipy.special.betainc` + `scipy.ndimage` |

`learn.PreflopStats` (`learn.py:197-252`) agrega por `player`, nunca por `pos`:
la posición se captura en `PreflopEvent.pos` y se descarta al agregar.

---

## 7. Resumen de problemas

**Sobre el cableado**

1. `BASE_WEIGHT_MAP` y `_ACTION_PROBS` están fuera de la ruta de producción. La
   cadena taxonomía → peso → probabilidad se interrumpe después del segundo paso.
2. `preflop_matrices.json` es el prior efectivo de M1 y no se regenera desde datos.
3. `opening_range` (sin perfil) usa el prior sin shrinkage: si cae en `FLAT_PRIOR`
   o en una tabla ausente, la decisión sale de constantes, no del histórico.

**Sobre los datos**

4. Los 5 artefactos derivados están desfasados; falta ~75% de las observaciones.
5. `fold` no tiene tabla de prior: `FLAT_PRIOR = 0.15` uniforme en las 169 celdas.
   Es la acción más frecuente (43% de la muestra) y la única con modelo plano.
6. `OR_BB` no existe; BB es la posición con más decisiones.
7. La posición nunca entra en los contadores de M1.
8. `other` = 34.5% de la muestra.

**Sobre la estadística**

9. `DEFAULT_ALPHA = 2.0` es idéntico en M1 y M5, sin justificación derivada de la
   muestra. Lo que sí depende de `n` es el fade-in (`min(1, n/20)`).
10. El `n` de M2 se usa para el fade-in pero no para la significación de la celda:
    no hay umbral de confianza que degrade a un nivel de evidencia superior.

**Sobre consistencia**

11. `_ACTION_PROBS` tiene `b >= r` en 38/38 y `'r'` nunca es la clave máxima. La
    codificación de las 4 claves no está documentada y no coincide con las
    categorías de `learn.py`.

---

## 8. Conclusión

Los mecanismos de calibración **existen y están bien construidos**: comparten una
estadística coherente (encogimiento a prior con pseudo-conteos), degradan con
escasez de muestra en lugar de romperse, y el único que depende de la fuerza de
la mano (M5) está conceptualmente bien planteado.

El diagnóstico no es "faltan mecanismos", sino que **están desconectados de la
fuente de datos y de la ruta de decisión**:

- La capa que consume datos reales (M1) solo cubre preflop con mano conocida, no
  desglosa por posición, y no modela el fold.
- La capa que cubre todas las acciones (M2/M3) no depende de la mano.
- La capa que sí depende de la mano y de la acción a la vez (M5) solo existe
  postflop y depende de un Oracle desfasado.
- La capa que uniría todo (M1 con posición, M2 con mano) no está escrita.

Y el dato transversal que condiciona cualquier trabajo futuro: **con el 61% de
las celdas en n≤5 y `other` al 34.5%, el tamaño de muestra solo justifica
estimadores con shrinkage fuerte, no frecuencias directas.**