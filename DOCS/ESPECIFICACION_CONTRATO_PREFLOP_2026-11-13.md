# Especificación del contrato preflop canónico (2026-11-13)

**Estado:** diseño. No implementa, no modifica `motor/`, no cambia la ruta
live, no regenera artefactos y no activa multiway.

**Objetivo:** definir `PreflopDecision` como la única representación
contextual de la **primera decisión voluntaria del héroe** en preflop. Live,
entrenamiento, auditoría y shadow deben poder leer el mismo objeto.

**Base actual:** `motor/preflop_contract.py` ya contiene el estado estricto
(`PreflopContext`, `PreflopClassification`, `table_plan`). Esta especificación
lo consolida y cierra los huecos que hoy quedan repartidos entre contrato,
`asistente_live` y `learn`.

`table_plan` no conoce `hero_index`: usa el contexto final de la fuente que
recibe y no verifica que sea el prefijo. El llamador debe pasarle solo las
acciones anteriores al héroe; si se le pasa la mano completa, puede devolver
un plan posterior. El contrato canónico debe exigir el prefijo y suprimir el
plan cuando `first_decision` no sea resuelto.

## 1. Alcance

Incluye:

- primera decisión voluntaria del héroe;
- acciones anteriores, orden y posiciones;
- importes, ciegas y nivel vigente;
- categoría, denominador y tablas;
- estado de clasificación y de cobertura;
- procedencia y versión.

No incluye:

- decisiones postflop;
- segunda vuelta del héroe en preflop;
- elección de perfil o de rango;
- EV;
- recomendación.

La segunda decisión preflop puede usar el mismo estado, pero no forma parte de
este contrato de primera decisión.

## 2. Tipos conceptuales

### 2.1 `PreflopDecision`

```
PreflopDecision:
  # identidad
  schema_version
  hand_id
  hero_pos
  hero_index                 # índice de su primera acción voluntaria
  source                     # live | training | fixture | shadow

  # secuencia
  prior_actions: [PreflopAction]
  players_acted: [pos]
  action_order: [pos]        # orden efectivo observado
  players_at_table: [pos]
  active_positions: [pos]

  # ciegas y nivel
  bb
  sb
  ante
  blind_posts: [BlindPost]
  current_level
  bb_posted

  # estado antes de la acción
  raises_before
  limps_before
  callers_before
  last_aggressor
  last_aggressor_amount
  mandatory_bet_to_call
  voluntary_actions

  # acción del héroe
  action_code                # b/r/c/x/f/p/...
  amount
  amount_evidence            # ausente | inválido | cero | positivo
  is_blind
  short_limp
  raise_number

  # lectura
  category
  denom
  status                     # resolved | unresolved | non_decision
  reason
  tainted_reason

  # tablas
  decision_plan               # qué tablas consultar para decidir
  range_query                 # qué consulta describe la acción observada
  coverage                    # estado agregado + por consulta

  # procedencia
  raw_sequence_hash
  contract_version
  data_snapshot_hash
```

`prior_actions` no son strings: cada una conserva `index`, `pos`, `action`,
`amount`, `amount_evidence`, `is_blind`. `action_order` se deriva del orden
observado, no de una tabla fija de asientos.

### 2.2 `PreflopAction`

```
PreflopAction:
  index
  pos
  action
  amount
  amount_evidence
  is_blind
```

`p` es una posta; nunca una decisión. La ciega del BB puede venir como `b` o
`p` y se reconoce por `blind` o por estructura (BB, `b`/`p`, sin acción
voluntaria anterior).

### 2.3 `BlindPost`

```
BlindPost:
  pos
  amount
  is_blind
  source                   # recorder | structural
```

## 3. Reglas de clasificación

El estado se construye **antes** de la acción del héroe. La categoría sale del
estado y del importe, nunca del carácter aislado.

### 3.1 `b` y `r`: acciones agresivas

Ambos se tratan igual: la letra no decide; el importe y el contexto sí.

| Condición | Categoría | Denominador | Efecto en el estado |
|---|---|---|---|
| importe ausente o inválido | `unresolved` | — | no se inventa |
| `raises_before=0`, importe ≤ BB | `limp` (`short_limp=True`) | `no_raise` | `limps_before += 1`; no agresor |
| `raises_before=0`, importe > BB, sin limps | `open` | `no_raise` | `raises_before=1`; agresor |
| `raises_before=0`, importe > BB, con limps | `rol` | `no_raise` | `raises_before=1`; agresor |
| `raises_before=1`, importe > nivel, con callers | `squeeze` | `facing_open` | `raises_before=2`; agresor |
| `raises_before=1`, importe > nivel, sin callers | `3bet` | `facing_open` | `raises_before=2`; agresor |
| `raises_before=2`, importe > nivel | `4bet` | `facing_3bet` | `raises_before=3`; agresor |
| `raises_before=3`, importe > nivel | `5bet` | `facing_3bet` | `raises_before=4`; agresor |
| `raises_before>=4`, importe > nivel | `6bet_plus` | `facing_3bet` | `raises_before+=1`; agresor |
| importe ≤ nivel con `raises_before>0` | `unresolved` | — | `subida_sin_incremento` |
| importe 0 | `unresolved` | — | `importe_cero` |

Reglas:

- Un `b`/`r` de ≤ BB sin subida previa es **limpe corto**, no apertura.
- Un `b` después de una subida solo es agresión si incrementa el nivel; si no,
  es dato ambiguo.
- `squeeze` no es una letra: es una subida después de open + al menos un call.
- `rol` no es una letra: es una apertura después de limps.
- El `raise_number` se conserva aunque la categoría se mapee después para
  entrenamiento.

### 3.2 `c`: call

| Condición | Categoría | Denominador |
|---|---|---|
| `raises_before=0`, `limps_before=0` | `limp` | `no_raise` |
| `raises_before=0`, `limps_before>0` | `call_limp` | `no_raise` |
| `raises_before=1` | `call_open` | `facing_open` |
| `raises_before=2` | `call_3bet` | `facing_3bet` |
| `raises_before=3` | `call_4bet` | `facing_3bet` |
| `raises_before>=4` | `call_5bet_plus` | `facing_3bet` |

Un call no se convierte en `open` por venir después de un limpe corto. La
posición y el estado mandan.

### 3.3 `x`: check

| Condición | Categoría | Estado |
|---|---|---|
| BB, `raises_before=0` | `bb_check` | `resolved`, `no_raise` |
| posición distinta de BB | `check_non_bb` | `unresolved`, `check_fuera_de_BB` |
| BB con `raises_before>0` | `check_bb_facing_raise` | `unresolved`, `BB_no_puede_pasar_con_subida` |
| sin posición | `check_pos_unknown` | `unresolved`, `check_sin_posicion` |

No se hereda la deuda legacy de leer cualquier `x` como `bb_check`.

### 3.4 `f`: fold

| Condición | Categoría |
|---|---|
| `raises_before=0` | `fold` |
| `raises_before=1` | `fold_vs_open` |
| `raises_before=2` | `fold_vs_3bet` |
| `raises_before=3` | `fold_vs_4bet` |
| `raises_before>=4` | `fold_vs_5bet_plus` |

El fold es una decisión resuelta; no tiene rango observado (`no_range`), pero
sí puede tener tabla de decisión (por ejemplo, 3B/Call_OR antes de foldear).

### 3.5 `p` y ciegas

- `p` es posta, no decisión (`non_decision`).
- La ciega del BB no se cuenta como subida ni como limp.
- Una posta repetida de BB antes de acción voluntaria es `unresolved`
  (`posta_repetida`).
- Una ciega con importe anómalo no se corrige: se conserva y se declara.

## 4. Ambigüedad y `unresolved`

Son `unresolved`, sin categoría forzada:

- `accion_ausente`
- `accion_desconocida`
- `pos_ausente`
- `importe_ausente`
- `importe_invalido`
- `importe_cero`
- `subida_sin_incremento`
- `posta_repetida`
- `check_fuera_de_BB`
- `check_pos_unknown`
- `BB_no_puede_pasar_con_subida`
- `secuencia_ambigua:<razón>`
- `sin_decision`

Reglas:

- Un `unresolved` **no** elige tabla de decisión.
- Tampoco elige rango observado.
- Si una acción posterior depende de un estado tainted, el estado se propaga:
  no se hereda una categoría inventada.
- Un check inválido no mueve dinero; solo contamina el estado si la razón es
  de secuencia/importe/posición, no por el mero check.

## 5. Dos tablas, dos preguntas

`PreflopDecision` separa:

### 5.1 `decision_plan`

Responde: “si el héroe tuviera que decidir ahora, ¿qué tablas consultaría?”.
Se calcula con el contexto **antes** de la acción del héroe.

| Contexto | `table_raise` | `table_call` |
|---|---|---|
| `raises=0`, `limps=0` | `OR` | — |
| `raises=0`, `limps>0` | `ROL` | — |
| `raises=1` | `3B` | `Call_OR` |
| `raises=2` | `4B` | `Call_3B` |
| `raises=3` | `5B` | `Call_4B` |
| `raises=4` | — | `Call_5B` |
| `raises>=5` | — | — (`unsupported`) |

`decision_plan` solo es válido si `status=resolved`. Si el estado es ambiguo,
el plan es `unresolved`; no se consulta `OR` “porque el prefijo parecía
limpio”.

Si el héroe es BB y `raises_before=0`, la opción es check/raise, no `OR`: la
tabla `OR_BB` es `impossible` (`intentional_check_option`). No se usa `OR`
para el check de BB.

### 5.2 `range_query`

Responde: “¿qué consulta describe la acción que el héroe ejecutó?”. Se usa
para rango/entrenamiento, no para elegir la acción.

| Categoría | `range_query` |
|---|---|
| `open` | `(no_raise, open)` |
| `limp` | `(no_raise, limp)` |
| `rol` | `(no_raise, rol)` |
| `call_limp` | `(no_raise, call_limp)` |
| `call_open` | `(facing_open, call_open)` |
| `3bet` | `(facing_open, 3bet)` |
| `squeeze` | `(facing_open, squeeze)` |
| `4bet` | `(facing_3bet, 4bet)` |
| `call_3bet` | `(facing_3bet, call_3bet)` |
| `5bet`, `6bet_plus` | `no_table` |
| `fold`, `fold_vs_*`, `bb_check` | `no_range` |
| `unresolved` | `unresolved` |

No se usa `decision_plan` para representar el rango de un limp: elegiría
`OR`, que es la tabla de la decisión, no la del rango observado.

## 6. Cobertura en el contrato

Cada consulta de tabla lleva su estado:

```
Coverage:
  state: exact | alias | coverage_gap | impossible | unknown
  reason
  source_key
  alias_of
  fallback_used
  fallback_key
```

- `exact`: clave exacta.
- `alias`: alias declarado y auditable.
- `coverage_gap`: la tabla debería existir y no existe.
- `impossible`: no aplica por orden de acción o por regla del juego; incluye
  ausencias intencionales (`OR_BB`, `ROL_UTG`) con razón explícita.
- `unknown`: no se pudo clasificar la acción o la cobertura.

La ausencia de tabla no es frecuencia 0. Un `RangeState` vacío es válido como
“no hay rango”, pero debe llevar `empty_reason` y ningún consumidor puede
tratarlo como masa real.

## 7. Invariantes

1. `hero_pos` y `hero_index` apuntan a la primera decisión voluntaria.
2. `prior_actions` son exactamente las acciones con índice menor que
   `hero_index`.
3. `raises_before`, `limps_before` y `callers_before` son los del estado
   anterior, no los finales.
4. `last_aggressor` es el último agresor real, no el último `b`/`r` bruto.
5. `decision_plan` es `None`/`unresolved` si la clasificación no es resuelta.
6. `range_query` es `None` si la categoría no tiene rango.
7. `category` y `denom` no se cambiar para que una métrica cuadre.
8. `coverage` viaja con la consulta; no se deduce después mirando el nombre.
9. La serialización es estable: mismos inputs → mismo `raw_sequence_hash` y
   mismo dict, salvo campos de procedencia.
10. `schema_version` y `contract_version` son obligatorios.

## 8. Ejemplos canónicos

| Caso | Acción | Categoría | `decision_plan` | `range_query` | Cobertura |
|---|---|---|---|---|---|
| Apertura | `UTG b 2.5` | `open` | `OR` | `(no_raise, open)` | exact |
| Limpe corto | `MP b 1.0` | `limp`, short | `OR` | `(no_raise, limp)` | exact |
| Limp normal | `SB c 1.0` | `limp` | `OR` | `(no_raise, limp)` | exact |
| Rol | `SB r 5.0` tras limp | `rol` | `ROL` | `(no_raise, rol)` | exact |
| Call open | `MP c 2.5` tras UTG | `call_open` | `3B/Call_OR` | `(facing_open, call_open)` | 3B exact, Call_OR gap |
| 3bet | `CO r 8.0` tras UTG | `3bet` | `3B/Call_OR` | `(facing_open, 3bet)` | 3B exact, Call_OR gap |
| Squeeze | `BB r 9.0` tras open+2 calls | `squeeze` | `3B/Call_OR` | `(facing_open, squeeze)` | exact |
| 4bet | `CO r 22.0` tras open+3bet | `4bet` | `4B/Call_3B` | `(facing_3bet, 4bet)` | exact o gap |
| Fold vs 3bet | `BB f` tras 3bet | `fold_vs_3bet` | `4B/Call_3B` | `no_range` | 4B/Call_3B gap |
| Check BB | `BB x` sin raise | `bb_check` | `ROL`/`OR` | `no_range` | exact/según contexto |
| Check inválido | `BTN x` | `check_non_bb` | **ninguno** | `unresolved` | unknown |
| Importe ausente | `UTG b None` | `unknown` | **ninguno** | `unresolved` | unknown |

## 9. Lo que no se hace

- No se usa el número de diferencias con legacy para forzar una categoría.
- No se convierte `unresolved` en `open`.
- No se usa `_preflop_spot` como fuente de decisión.
- No se interpreta un `b` corto como apertura.
- No se lee `r` como 3bet por la letra; se lee por el estado.
- No se mezcla `decision_plan` con `range_query`.
- No se cambia la ruta live en esta fase.
