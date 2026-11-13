# Escenarios de referencia HU (2026-11-13)

**Estado:** especificación de fixtures. No implementa un harness, no cambia
código, no escribe datos y no valida todavía contra una nueva versión.

**Objetivo:** fijar casos con estado, categoría, tablas, cobertura y
frecuencias esperadas para comparar contrato, legacy y sombra.

Los escenarios reales están tomados de la base congelada por
`DOCS/DISCREPANCIAS_AUDITORIA_2026-11-13.md`. Si la base cambia, los IDs
pueden dejar de coincidir; el fixture debe guardar hash de snapshot y copia
mínima de la secuencia, no depender de la sesión viva.

## 1. Regla de comparación

Cada escenario declara:

- `source`: `real` o `synthetic`;
- `hand_id` cuando aplica;
- `hero_pos`;
- secuencia mínima;
- `context`: `raises_before / limps_before / callers_before`, `vs` y último
  agresor;
- `category` y `denom`;
- `decision_plan`;
- `range_query`;
- `coverage` de cada tabla;
- `legacy` esperado, si existe;
- `frequency` observada, si la celda es válida.

`decision_plan` se especifica **canónico**: si `status=unresolved` o
`non_decision`, no hay tabla que consultar. El `table_plan` actual puede
devolver un plan de prefijo; eso no es el comportamiento canónico y el fixture
debe detectarlo.

## 2. Escenarios reales

Abreviaturas: `R/L/C` = raises/limps/callers antes de la acción. `Plan` =
`tabla_raise/tabla_call`. `Cov` = cobertura de esas tablas; `gap` =
`coverage_gap`. `fallback_other_vs` no es un estado: es un `gap` con
aproximaci?n de otro rival.

| ID | Mano/pos | Secuencia / acción | Contexto | Categoría | Plan | Cov | Range query |
|---|---|---|---|---|---|---|---|
| R01 | `H_0001/UTG` | `UTG b 2.5` | `0/0/0` | `open` | `OR` | exact | `(no_raise, open)` |
| R02 | `H_0001/MP` | `UTG b 2.5`, `MP c 2.5` | `1/0/0` vs UTG | `call_open` | `3B/Call_OR` | exact/gap | `(facing_open, call_open)` |
| R03 | `H_0002/MP` | `UTG c 1.0`, `MP f` | `0/1/0` | `fold` | `ROL` | exact | `no_range` |
| R04 | `H_0003/CO` | `UTG b 2.5`, `CO f` | `1/0/0` vs UTG | `fold_vs_open` | `3B/Call_OR` | exact/gap | `no_range` |
| R05 | `H_0005/SB` | `UTG c`, `MP c`, `CO c`, `SB c 1.0` | `0/3/0` | `call_limp` | `ROL` | exact | `(no_raise, call_limp)` |
| R06 | `H_0012/BB` | limps previos, `BB x` | `0/2/0` | `bb_check` | `ROL` | exact | `no_range` |
| R07 | `H_0022/CO` | `UTG b`, `CO r 8.0` | `1/0/0` vs UTG | `3bet` | `3B/Call_OR` | exact/gap | `(facing_open, 3bet)` |
| R08 | `H_0032/SB` | `UTG c 1.0`, `SB r 5.0` | `0/1/0` | `rol` | `ROL` | exact | `(no_raise, rol)` |
| R09 | `H_0033/SB` | `SB c 1.0` | `0/0/0` | `limp` | `OR` | exact | `(no_raise, limp)` |
| R10 | `H_0066/SB` | folds previos, `SB r 3.0` | `0/0/0` | `open` | `OR` | exact | `(no_raise, open)` |
| R11 | `H_0124/BB` | 3bet previo, `BB f` | `2/0/0` vs BTN | `fold_vs_3bet` | `4B/Call_3B` | gap/gap | `no_range` |
| R12 | `H_0130/SB` | 3bet previo, `SB c` | `2/0/0` vs BTN | `call_3bet` | `4B/Call_3B` | gap+fallback_other_vs / gap+fallback_other_vs | `(facing_3bet, call_3bet)` |
| R13 | `H_0135/BB` | open + 2 calls, `BB r 9.0` | `1/0/2` vs MP | `squeeze` | `3B/Call_OR` | exact/exact | `(facing_open, squeeze)` |
| R14 | `H_0004/MP` | `MP b 1.0` | `0/0/0` | `limp` (short) | `OR` | exact | `(no_raise, limp)` |
| R15 | `H_0056/BTN` | `BTN x` sin BB | `0/0/0` | `check_non_bb` | **ninguno** | unknown | `unresolved` |
| R16 | `H_0357/SB` | `SB b 3.0` no incremental | tainted | `unknown` | **ninguno** | unknown | `unresolved` |
| R17 | `H_0266/BB` | sin decisión | `sin_decision` | `unknown` | **ninguno** | unknown | `unresolved` |

Notas:

- R14 conserva `short_limp=True`.
- R12 usa `fallback_other_vs`; su estado sigue siendo `coverage_gap` y no debe contarse como `exact`.
- R15–R17 son trazabilidad: no hay plan, aunque el prefijo pudiera parecer
  limpio. Razones: R15 `check_fuera_de_BB`, R16
  `secuencia_ambigua:subida_sin_incremento`, R17 `sin_decision`.
- R11 es un fold resuelto: no tiene rango, pero sí plan de decisión.
- R02/R04/R07 comparten el hueco `Call_OR`; no son el mismo caso de acción.

## 3. Escenarios sintéticos

Secuencias mínimas; `hero_pos` es la posición cuya primera decisión se evalúa.

| ID | Secuencia | `hero_pos` | Esperado |
|---|---|---|---|
| S01 | `UTG b 1.0` | UTG | `limp`, `short_limp=True`, plan `OR`, range `(no_raise, limp)` |
| S02 | `UTG b 2.5`, `BB x` | BB | **unresolved** `BB_no_puede_pasar_con_subida`; sin plan |
| S03 | `UTG b None` | UTG | **unresolved** `importe_ausente`; sin plan |
| S04 | `UTG b 0` | UTG | **unresolved** `importe_cero`; sin plan |
| S05 | `UTG b 2.5`, `MP r 2.5` | MP | **unresolved** `subida_sin_incremento`; sin plan |
| S06 | `BB p 1.0`, `BB p 1.0` | BB | **unresolved** `posta_repetida`; sin plan |
| S07 | `{'pos':'', 'action':'b','amount':2.5}` | `''` | **unresolved** `pos_ausente`; sin plan |
| S08 | `UTG b 2.5`, `MP r 8`, `CO r 22`, `BTN r 55` | BTN | `5bet`, plan `5B/Call_4B`, cov exact/exact, range `no_table` |
| S09 | `UTG c 1.0`, `MP c 1.0`, `CO r 5.0` | CO | `rol`, plan `ROL` (exact), range `(no_raise, rol)` |
| S10 | `UTG b 2.5`, `MP c`, `CO c`, `BTN r 11` | BTN | `squeeze`, plan `3B/Call_OR` (exact/exact), range `(facing_open, squeeze)` |
| S11 | `UTG b 2.5`, `MP r 8`, `CO r 22` | CO | `4bet`, plan `4B/Call_3B` (gap+fallback_other_vs / gap+fallback_other_vs), range `(facing_3bet, 4bet)` |
| S12 | `UTG b`, `MP r`, `CO r`, `BTN c` | BTN | `call_4bet`, plan `5B/Call_4B` (exact/exact), range `(facing_3bet, call_4bet)` |
| S13 | `UTG b`, `MP r`, `CO r`, `BTN r`, `SB r`, `BB r` | BB | `6bet_plus`, plan **unsupported** (`raises_before=5`) |
| S14 | `UTG b 2.5`, `MP r 8`, `CO c`, `BTN r 25` | BTN | `4bet` (raises=2), plan `4B/Call_3B`, range `(facing_3bet, 4bet)`; el caller no lo convierte en squeeze |

S13: el contrato no ofrece `6B`; `raises_before=5` deja el plan de decisión
sin tabla. No se convierte en `5B` ni se usa una tabla de otro nivel.

## 4. Fixture de alias (solo lookup)

Este caso no es una primera decisión; prueba la cobertura.

| ID | Consulta | Esperado |
|---|---|---|
| L01 | `_pf_table_lookup('4B','UTG','MP')` | `alias` a `4B_UTG_vs_HJ`, `source_key` visible |
| L02 | `_pf_table_lookup('OR','BB',...)` | `impossible` (`OR_BB`/check option) |
| L03 | `_pf_table_lookup('Call_OR','MP','UTG')` | `coverage_gap` |
| L04 | `_pf_table_lookup('4B','BTN','CO')` | `coverage_gap` + `fallback_other_vs`, no `exact` |
| L05 | acción sin posición | `unknown` |

## 5. Comparación con legacy

Para cada escenario real se registra:

- categoría canónica vs `_preflop_spot`/`_preflop_raises` legacy;
- tabla canónica vs `_pf_table_lookup`;
- acción elegida por cada ruta, si hay recomendación;
- diferencia: `classification`, `table`, `action`, `coverage` o
  `no_comparable`;
- acción legacy y cobertura legacy.

No se exige paridad total. Se exige que toda diferencia esté explicada y que
ningún `unresolved` se haya convertido en una categoría con tabla.

## 6. Frecuencias y EV

- Una frecuencia solo se compara si la celda canónica es `exact` o `alias`.
- `coverage_gap`, `impossible`, `unknown` y `fallback_other_vs` no entran en
  la misma celda que `exact`.
- El EV se etiqueta con método, `n`, seed y cobertura; no se compara un EV
  con equity de otra fuente.
- No se declara ganador por una suma agregada sin mirar escenarios y
  distribución.

## 7. Criterios de aceptación de la fase

1. Los 17 reales + 14 sintéticos tienen estado/categoría esperados.
2. R15–R17 no consultan tabla en el contrato canónico.
3. R02/R04/R07 no usan `Call_OR` como si existiera.
4. R11/R12 distinguen `gap` sin fallback de `gap` con fallback.
5. S01–S07 no inventan categoría ni tabla.
6. S08–S13 respetan niveles y límites.
7. Cada fixture guarda snapshot y versión de contrato.
8. Cualquier cambio posterior de expected es visible en el diff, no silencioso.
