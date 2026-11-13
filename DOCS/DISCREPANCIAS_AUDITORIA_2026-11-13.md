# Discrepancias de la auditoría estratégica HU/MW (2026-11-13)

**Estado:** verificación read-only terminada. No se modificó código, datos ni
artefactos derivados. No se activó nada.

**Informe verificado:** `DOCS/AUDITORIA_ESTRATEGICA_MULTIWAY_2026-11-13.md`.

**Instrumento:** `tools/auditar_estrategia_reproducible.py`.

**Commit:** `8197eeecbf02a5a062382cca8c23b099eba42342`.

**Base:** `data/hands_db.jsonl`, 1.344 manos, SHA-256
`3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e`.

## 1. Regla de esta verificación

Cada cifra se reproduce con una definición explícita de denominador, filtro,
origen y función. Si el resultado no coincide con el informe, se marca
`DOES_NOT_REPRODUCE` y se documenta. No se ajusta el código ni los datos para
forzar la coincidencia.

Reproducir:

```powershell
python tools/auditar_estrategia_reproducible.py
python tools/auditar_estrategia_reproducible.py --json
```

El script solo lee. No llama a `--apply`, no abre writers, no escribe en
`data/` y no cambia `MULTIWAY_SOPORTADO`.

## 2. Resumen de discrepancias

| Medición | Informe | Reproducido | Estado | Lectura |
|---|---:|---:|---|---|
| Eventos preflop | 7.107 | 7.107 | OK | `learn.preflop_events`; base completa |
| Acciones `b` crudas | 178 (162 > 1 BB) | 178 / 162 | OK | No todas las `b` son aperturas válidas |
| Divergencias totales `_preflop_spot` | 468 | **6.233** | NO | 468 es **un par**, no el total |
| Divergencias `_preflop_raises` + limp | 468 / 431 / 37 | **211 / 177 / 6** | NO | El total y los subconjuntos no coinciden |
| Plan `table_plan` | 3.065 / 1.563 / 2.329 / 147 / 3 | **5.355 / 812 / 915 / 23 / 2** | NO | No es la distribución de `table_plan` |
| `facing_open` estricto | 2.329 | **2.331** | NO (off-by-2) | Diferencia mínima, no metodológica |
| `facing_open` exacto | 1.249 | **1.251** | NO (off-by-2) | La cobertura total 1.080 sí coincide |
| `Call_OR` sin cobertura | 1.080 | 1.080 | OK | 1.079 `missing` + 1 `fallback_other_vs` |
| `facing_3bet` estricto | 147 | 147 | OK | `fold_vs_3bet` 131 + `call_3bet` 16 |
| `4B` sin tablas | 78 | 78 | OK | `4B` y `Call_3B` ambas `missing` |
| Legacy vs entrenamiento | 54 distintos / 44 unresolved | 54 / 44 | OK | El contrato estricto no resuelve 44 |
| Prior plano, todos | 1.881 / 2.396 (78,5 %) | 1.881 / 2.396 (**78,5058 %**) | OK | Incluye al hero |
| Prior plano, villanos | 1.881 / 2.396 (78,5 %) | **1.572 / 1.992 (78,9157 %)** | NO semántico | El informe llama “villanos” a una base con hero |
| Combos efectivos limp BB | 939 | **948,52** | NO | `(Σw)² / Σw²` sobre `prob_vec` |
| Multiway total | 399 / 894 = 44,63 % | 399 / 894 = 44,6309 % | OK | `metrica_politica` |
| Multiway fiable | 210 / 506 = 41,50 % | 210 / 506 = 41,502 % | OK | `reliable_only=True` |
| Equity flush draw | 0,596207 → 0,726362 | 0,596207 → 0,726362 | OK | 200 runouts, 200 combos, seed 7 |
| Equity overpair | 0,966235 → 0,855701 | 0,966235 → 0,855701 | OK | Igual |
| Equity gutshot | 0,181776 → 0,304762 | 0,181776 → 0,304762 | OK | Igual |
| Cobertura estática de tablas | 107/1/2/82/30/0 | 107/1/2/82/30/0 | OK | `audit_engine_coverage` |

## 3. Discrepancia principal: el 468

El informe usa **468** como “divergencias totales” entre la lectura legacy y
el contrato. Ese número existe, pero no es un total: es un único par de
etiquetas.

Medición reproducible:

- `first_decision` estricto resuelve 7.063 eventos; 44 quedan unresolved.
- `_preflop_spot` legacy difiere del contrato estricto en **6.233 eventos**.
- El par `(facing_open, call_open) -> (no_raise, limp)` aparece **468 veces**.

Pares principales:

| Veces | `_preflop_spot` legacy | `first_decision` estricto |
|---:|---|---|
| 2.365 | `(no_raise, open)` | `(no_raise, fold)` |
| 1.580 | `(no_raise, open)` | `(facing_open, fold_vs_open)` |
| **468** | `(facing_open, call_open)` | `(no_raise, limp)` |
| 448 | `(facing_open, 3bet)` | `(no_raise, open)` |
| 320 | `(facing_open, call_open)` | `(no_raise, call_limp)` |
| 315 | `(no_raise, limp)` | `(no_raise, bb_check)` |
| 233 | `(facing_open, 3bet)` | `(no_raise, rol)` |
| 131 | `(no_raise, open)` | `(facing_3bet, fold_vs_3bet)` |
| 127 | `(no_raise, open)` | `(no_raise, limp)` |
| 48 | `(facing_open, call_open)` | `(no_raise, open)` |
| 48 | `(no_raise, open)` | `(no_raise, rol)` |
| 44 | `(no_raise, open)` | `(no_raise, call_limp)` |

La diferencia dominante es semántica: `_preflop_spot` interpreta la **primera
acción** y no el estado relativo al hero. Por eso convierte miles de spots
“sin subida” en `open`, y no distingue `fold`, `fold_vs_open`, `bb_check`,
`call_limp` o `limp`. No es un desajuste de redondeo.

**Consecuencia:** no usar 468 como titular de divergencias. El titular
correcto es 6.233 diferencias de etiqueta, con 468 como un par concreto.

## 4. Discrepancia de `_preflop_raises` y limp

El informe habla de 468 totales, 431 dobles (`n` y `vs`) y 37 simples (`n`).
La reproducción sobre los 7.105 eventos resueltos de `table_plan` da:

| Medición | Valor |
|---|---:|
| Resueltos | 7.105 |
| Unresolved | 2 |
| Cualquier diferencia (`n`, `limp` o `vs`) | **211** |
| Solo `n_raises` | **183** |
| Solo `vs_pos` | **177** |
| `n` y `vs` | **177** |
| Solo `limp` | **51** |
| Solo `n`, sin `limp` ni `vs` | **6** |
| `n` y sin limp (`n_only_no_limp`) | **6** |

El “431” no aparece en esta lectura. El “37” tampoco: el subconjunto de solo
`n` es 6. La diferencia es compatible con haber mezclado el 468 de
`_preflop_spot` con el conteo de `_preflop_raises`; no se puede atribuir a una
sola función sin el instrumento original.

## 5. Discrepancia de la distribución de planes

`table_plan` sobre el prefijo estricto antes de cada primera decisión produce:

| Grupo | Informe | Reproducido |
|---|---:|---:|
| `OR` | 3.065 | **5.355** |
| `ROL` | 1.563 | **812** |
| `3B` / `Call_OR` (`facing_open`) | 2.329 | **915** |
| `4B` / `Call_3B` | 147 | **23** |
| Unresolved | 3 | **2** |

Los 2 unresolved son `('unresolved', 'subida_sin_incremento')`.

La coincidencia del informe con 2.329 y 147 sugiere que esas dos cifras se
tomaron del **denominador de eventos** (`first_decision`), no de
`table_plan`: el denominador estricto es 2.331 `facing_open` y 147
`facing_3bet`. Pero 3.065 y 1.563 no salen de `table_plan` actual. No se
identificó el instrumento exacto; queda como discrepancia de procedencia.

## 6. Off-by-2 en `facing_open`

`first_decision` estricto produce:

- `facing_open = 2.331` (informe: 2.329).
- `3B` exacta y `Call_OR` exacta = 1.251 (informe: 1.249).
- Sin `Call_OR` = 1.080 (informe: 1.080).

La cobertura total coincide; las dos primeras cifras difieren en 2. Es un
desajuste de conteo, no un cambio de política. No se corrigió el informe
original: queda registrado aquí.

## 7. Prior posicional: el denominador incluye al hero

La reproducción confirma el 1.881 / 2.396 = **78,5058 %** (el informe redondea
a 78,5 %). Pero ese denominador es el conjunto de **todos** los jugadores con
alguna acción postflop, no solo villanos:

| Base | Jugadores | Flat | Tabla | % flat |
|---|---:|---:|---:|---:|
| Todos, incluido hero | 2.396 | 1.881 | 515 | 78,5058 |
| Solo villanos | **1.992** | **1.572** | 420 | **78,9157** |

El uso de `FLAT_PRIOR` sigue siendo masivo en ambos casos. La diferencia no
cambia la conclusión, pero el informe no debe presentar 2.396 como “villanos”.

Fuentes principales de `FLAT_PRIOR` (todos):

| Veces | `(acción, posición, vs)` |
|---:|---|
| 313 | `('limp', 'BB', '')` |
| 194 | `('call_open', 'SB', '')` |
| 113 | `('call_open', 'BTN', '')` |
| 109 | `('call_open', 'CO', '')` |
| 92 | `('3bet', 'BTN', '')` |
| 91 | `('3bet', 'MP', '')` |
| 87 | `('3bet', 'CO', '')` |
| 86 | `('call_open', 'MP', '')` |

## 8. Combos efectivos

El informe da 939 para el prior plano `limp/BB`. La fórmula
`(Σw)² / Σw²` sobre `ProfileRangeModel.prob_vec` da **948,5188**.

Otras comprobaciones:

| Caso | Combos efectivos |
|---|---:|
| TIBURON `facing_open` / `3bet` / UTG / vs vacío | 759,0885 |
| TIBURON `facing_open` / `call_open` / CO / vs BTN | 816,6725 |
| TIBURON `no_raise` / `limp` / BB / vs vacío | **948,5188** |

No se ajustó el prior.

## 9. Cifras que sí se reproducen

- **Eventos preflop:** 7.107.
- **`b` crudas:** 178; 162 con importe > 1 BB; 16 <= 1 BB.
- **Secuencia estricta de categorías:**
  `fold` 2.365; `fold_vs_open` 1.580; `call_open` 636; `open` 633; `limp`
  605; `call_limp` 367; `bb_check` 315; `rol` 300; `fold_vs_3bet` 131;
  `3bet` 89; `squeeze` 26; `call_3bet` 16; unresolved 40
  `check_non_bb` + 4 `unknown`.
- **Entrenamiento:** 7.009 iguales, 54 distintos, 44 unresolved.
- **Multiway:** 399 / 894 = 44,63 %; fiable 210 / 506 = 41,50 %.
- **Equity:** los tres casos del informe, con 200 runouts, 200 combos y seed 7.
- **Perfiles:** TIBURON `no_raise` 654/166, `facing_open` 312/141,
  `facing_3bet` 16/15; PEZ 128/84, 55/43, 5/5; `3bet` TIBURON 22/11 y PEZ 4/3.
- **Rutas:** `MULTIWAY_SOPORTADO=False`; la ruta live usa `prob_vec`, no
  `prob_vec_player` ni `player_omega`; no importa `recommend`; importa
  `_equity_vs_rival`. `recommend_loop` define `recommend`, tiene
  `_build_multiway_range` y usa `union`.

## 10. Qué no se ha hecho

- No se ha modificado `DOCS/AUDITORIA_ESTRATEGICA_MULTIWAY_2026-11-13.md`.
- No se ha alterado `motor/`.
- No se ha escrito en `data/`.
- No se ha regenerado ningún modelo.
- No se ha activado `MULTIWAY_SOPORTADO`.
- No se ha declarado corregido ningún defecto por el hecho de reproducir una
  cifra.

## 11. Snapshot de artefactos

| Archivo | Bytes | SHA-256 |
|---|---:|---|
| `data/hands_db.jsonl` | 2.070.355 | `3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e` |
| `data/preflop_matrices.json` | 328.548 | `075bae3aa9de8f6141c5db016a397a9b34d727ffbed4b6a5512d108c27f0e5c1` |
| `data/behavior.json` | 27.908 | `efe7b9d65322355bdc6128fb5a3ad2b8f16455827e19d41a1109b70d40497cae` |
| `data/postflop_ranges.json` | 13.709 | `1db355f997998c698b6968de615c45f3db7228f58ff8ee3b622c63427f08e64c` |
| `data/profile_ranges.json` | 90.334 | `add0e8999cb713e2c739369baccddcded9164ef69d55b01c8240419648b620aa` |
| `data/decisions.jsonl` | 8.903.510 | `c6f8a18db358f3071fab7d5c4a17d3e1fdd88d17c54ce345592af9b5dd7ab841` |
| `data/observations.json` | 4.738.786 | `86ab8c2dda562790bd946cc61a5126c1e114d1625bf7adc38cfd30a0d1a721e3` |

El script imprime estos hashes y el commit en cada ejecución. Si cambia un
hash, la reproducción debe repetirse antes de usar cualquier cifra.
