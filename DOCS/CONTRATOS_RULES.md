# Contratos de `rules.py` — F5

**Bloque:** F5 · **Base:** `1b14c18` + reconstrucción `87cdde7`
**Tests:** `motor/test_rules_contratos.py` (17 contratos)
**Inventario:** `tools/inventario_rules.py`

Este documento formaliza lo que `rules.py` **promete hoy**. No se ha cambiado la
implementación: se fija el comportamiento vigente para que cualquier cambio
posterior sea deliberado y detectable.

---

## 1. Inventario de la superficie pública

12 símbolos. **5 son la superficie real** (tienen consumidores); el resto son
internos dejados visibles.

| símbolo | tipo | prod | test | estado |
|---|---|---|---|---|
| `plan` | función | 2 | 2 | ✅ contrato definido |
| `select_best` | función | 2 | 2 | ✅ contrato definido |
| `RulePlan` | clase | 2 | 0 → **17** | ✅ contrato definido |
| `board_class` | función | 0 | 1 | ✅ contrato definido |
| `RULES` | const | 0 | 1 | tabla de reglas |
| `CBET_SIZES`, `BARREL_SIZES`, `DONK_SIZES`, `PROBE_SIZES`, `VALUE_SIZES` | const | 0 | 0 | ⚠️ sin consumidor |
| `Ctx`, `Row` | clase | 0 | 0 | ⚠️ sin consumidor |

**Consumidores reales** (verificados, no por coincidencia de texto):

- `plan` → `recommend_loop.py`, `asistente_live.py` (importada como `rules_plan`)
- `select_best` → `recommend_loop.py`, `asistente_live.py` (`rules_select_best`)
- `RulePlan` → `recommend_loop.py`, `panel.py` (como tipo de un parámetro)
- `decision.py` **no** importa nada de `rules`: solo lo menciona en docstrings

⚠️ `tools/inventario_rules.py` marca `panel.py` como consumidor de `plan`,
pero es un **falso positivo**: `plan` ahí es un *nombre de parámetro*, no una
llamada.

---

## 2. Contratos

### C1 — `board_class(board) -> 'DRY' | 'SEMI_DRY' | 'WET' | None`

- **Precondición:** `board` es una lista de 3, 4 o 5 códigos de carta.
- **Postcondición:** devuelve `None` si el board está incompleto. **Nunca
  inventa textura** ante board parcial.
- **Invariante:** dominio cerrado; la función es **idempotente** y no depende
  del orden de las cartas más allá de la textura.

### C2 — `plan(...) -> RulePlan`

- **Precondiciones:** `street ∈ {'flop','turn','river'}` y board completo.
- **Postcondición:** devuelve siempre un `RulePlan`. Nunca `None`.
- **Errores:** `street='preflop'` → `ValueError`. `street` desconocido →
  `ValueError` o `KeyError`.
- **Determinismo:** mismas entradas → mismo plan. Sin azar ni reloj.

> ⚠️ **Defecto conocido que este contrato fija:** `recommend_loop` captura ese
> `ValueError`, imprime a stderr y pone `rp = None`, con lo que **se pierde todo
> el filtrado de reglas**. La ruta de producción (`asistente_live:1021`) evita el
> preflop, pero el riesgo sigue vivo en la llamada directa. Ver
> `PROYECTO.md` §6.1.

### C3 — `RulePlan`: invariantes

| invariante | estado |
|---|---|
| `candidates` es tupla **no vacía** | ✅ verificado |
| `candidates` contiene `'fold'` solo si `to_call > 0` | ✅ verificado |
| cada `bet_sizes` es `float` en `(0, 1.5]` | ✅ verificado |
| `note` y `spot` son `str` | ✅ verificado |
| existen `bet_sizes`, `raise_to`, `raise_all_in`, `paired`, `structure`, `n_players` | ✅ verificado |

> **Por qué "candidates no vacío" es importante:** si se vaciara,
> `select_best` solo tendría `'fold'` en su lista y devolvería un *fold*
> silencioso, sin explicar por qué. Es exactamente el defecto descrito en
> `PROYECTO.md` §6.1, y este contrato lo hace detectable.

### C4 — `select_best(evs, rp) -> (label, value)`

- **`rp is None`** → equivale a `evs.best()` sobre **todas** las acciones.
- **`rp` dado** → la etiqueta devuelta está **siempre** en `rp.candidates`.
- **Baseline del fold:** es el **EV real** de `ev['fold']`, no `0.0`. Con todas
  las acciones peor que el fold, devuelve `('fold', <valor real>)`, aunque sea
  negativo. Devolver `0.0` sería inventar un número.
- **Acciones ausentes:** una clave que no está en `evs.ev` no se elige.
- **EV no finito (NaN, ±inf):** no es un EV. Se
  **ignora** como candidato. Sin esto, un `fold` con NaN hace que
  toda comparación dé False y el bucle no mejore
  nunca: devolvía ('fold', nan) teniendo un `check` real.
- **Ningún EV finito** (tabla vacía o toda NaN):
  **lanza `EvInvalido`**, subclase de `ValueError`.
  No devuelve una acción por defecto: «no hay datos
  para decidir» y «fold es la mejor acción» son
  cosas distintas.
- **Empate:** gana el primero, y `fold` se considera siempre primero.

> **Firmado.** Opción (b). El texto largo, con el porqué
> de no haber elegido (a) ni (c), en
> [`CONTRATO_C4.md`](CONTRATO_C4.md).

### C5 — Compatibilidad con los consumidores

`recommend_loop` consume `candidates`, `bet_sizes`, `raise_to`, `note` y
`spot`; `panel` consume `note` y `spot`. El contrato C3 obliga a que todos esos
atributos existan siempre, incluso con `bet_sizes` vacío.

---

## 3. Condición previa a F6/Fase D (revision_2)

Se comprobó si `bb_check` afecta a algún contrato que F5 formalice.

**No.** `rules.py` no menciona `bb_check` en ningún punto: es un motor de
decisión **postflop**, mientras que `bb_check` es una categoría **preflop**
(`CATEGORY_DENOM['bb_check'] = 'no_raise'`).

Por tanto la migración de los 41 `bb_check` pendientes
(`DOCS/CORRECCIONES_MANUALES.md`, CM-003) **no bloquea F5**, y F5 no altera su
semántica. Sí debe cerrarse antes de la **Fase D (calibración)**.

---

## 4. Pendientes que este bloque NO resuelve

Están documentados y ahora tienen contrato, pero **sin cambiar**:

1. `nut_advantage` se pasa a `Ctx` y **nunca se consulta** (0 condiciones).
2. `villain_bet_flop` se pasa y **nunca se consulta**.
3. `_en_flop_ip` significa "no fui el agresor preflop", **no** "soy IP".
4. `plan()` lanza en preflop y `recommend_loop` degrada a `rp = None`.
5. `CBET_SIZES`…`VALUE_SIZES`, `Ctx` y `Row` no tienen consumidor.

Cada uno requiere una decisión de diseño (usar, o eliminar el parámetro), no un
arreglo mecánico. Por eso quedan fuera de este bloque.