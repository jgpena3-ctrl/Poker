# P0-1 — CONTRATO ÚNICO DE INTERPRETACIÓN PREFLOP

> **Estado: SOMBRA.** El contrato nuevo se ejecuta, se registra y se compara,
> pero **no sustituye** a `_preflop_spot`, `_preflop_raises` ni a
> `_recom_preflop`. La recomendación visible no cambia. La activación exige
> autorización separada.

## 1. EL DEFECTO QUE CIERRA

El entrenamiento clasificaba una acción con el estado anterior de la
secuencia. El serving decidía por el último carácter:

| parser | regla real |
|---|---|
| `learn.classify_first_action` | `r` con 0 subidas = open; `r` con 1 = 3bet; `b` <= BB = limp; etc. |
| `asistente_live._preflop_spot` | `r` -> `3bet` siempre; `b` -> `open` siempre; `c` -> `call_open` siempre; `x` -> `limp` siempre |

Con esa regla, un `r` que abre el bote se servía como 3bet, un `b` de 1BB se
servía como apertura y un fold se servía como `open`. No es una diferencia de
precisión: es otra lectura de la mano.

## 2. SEMÁNTICA REAL DE LAS ACCIONES

Estas son las reglas que implementa `motor/preflop_contract.py`.

### 2.1 Códigos del recorder

| código | significado | ¿decisión? |
|---|---|---|
| `p` | posta de ciega (SB/BB o posta tardía) | **No** |
| `b` | acción agresiva. Puede ser apertura, subida sobre limpes, 3bet o limpe corto. **El código no decide la categoría.** | Sí |
| `r` | acción agresiva. Puede ser apertura si nadie subió, o resubida si ya hubo subida. **El código no decide la categoría.** | Sí |
| `c` | igualar. Es limp si no hay subida previa; call_open/3bet/4bet si la hay. | Sí |
| `x` | pasar. Solo es válido en BB sin subida vigente. | Sí |
| `f` | retirarse. | Sí |

### 2.2 Ciegas y `BB`

Una acción es ciega/post si:

1. trae `blind`/`is_blind` explícito, o
2. es `BB` con `b`/`p` y no hay ninguna acción voluntaria anterior.

Una `p` nunca crea un `PreflopEvent`: el jugador que posta sigue sin decidir.
La ciega antigua grabada como `BB b` tampoco crea decisión.

### 2.3 Estado previo que se conserva

Cada clasificación lleva un `PreflopContext` con:

- `raises_before`: subidas reales (no limpes cortos).
- `limps_before`: limpes, incluidos los limpes cortos `b <= BB`.
- `callers_before`: calls que ya enfrentaban la subida vigente (squeeze).
- `current_level`: nivel de la apuesta vigente.
- `aggressors` y `aggressor_amounts`: quién subió y cuánto, en orden.
- `bb_posted`, `blind_posts`, `voluntary_actions`, `players_acted`.
- `tainted_reason`: la secuencia quedó ambigua y las acciones siguientes no
  se pueden leer como si nada hubiera pasado.

### 2.4 Reglas de clasificación

| situación | categoría | denominador |
|---|---|---|
| `f` sin subida / con 1 / con 2 / con 3+ | `fold` / `fold_vs_open` / `fold_vs_3bet` / `fold_vs_4bet` (`fold_vs_5bet_plus`) | `no_raise` / `facing_open` / `facing_3bet` |
| `c` sin subida y sin limpes / con limpes | `limp` / `call_limp` | `no_raise` |
| `c` con 1 / 2 / 3 / 4+ subidas | `call_open` / `call_3bet` / `call_4bet` / `call_5bet_plus` | `facing_open` / `facing_3bet` |
| `b`/`r` <= BB sin subida | `limp` (limpe corto) | `no_raise` |
| `b`/`r` > BB sin subida, sin limpes / con limpes | `open` / `rol` | `no_raise` |
| `b`/`r` con 1 subida, sin callers / con callers | `3bet` / `squeeze` | `facing_open` |
| `b`/`r` con 2 / 3 / 4+ subidas | `4bet` / `5bet` / `6bet_plus` | `facing_3bet` |
| `x` en BB sin subida | `bb_check` | `no_raise` |
| `x` fuera de BB | `unresolved` (`check_non_bb`) | — |
| `x` en BB con subida | `unresolved` (`check_bb_facing_raise`) | — |
| falta importe en `b`/`r` | `unresolved` (`importe_ausente`) | — |
| subida que no sube el nivel | `unresolved` (`subida_sin_incremento`) | — |
| acción desconocida | `unresolved` (`accion_desconocida`) | — |

Un limpe corto **no** incrementa `raises_before` y **sí** incrementa
`limps_before`. Esa es la diferencia deliberada con la deuda histórica.

## 3. PARIDAD CON EL ENTRENAMIENTO

`learn.classify_first_action` sigue existiendo, pero ya es un adaptador:
llama a `legacy_training_category`, que usa el mismo contrato con
`legacy=True`. `preflop_events` recorre la secuencia con
`walk_preflop(legacy=True)`.

`legacy=True` reproduce la deuda histórica, no la esconde:

- un limpe corto `b` se clasifica `limp` pero se cuenta como subida para el
  jugador siguiente;
- un `x` de cualquier posición se lee como `bb_check`.

**Medido:** con la base completa, 7.107 eventos; con la ventana de 877,
4.594 eventos. La categoría, denominador, importe, `prereq` y agregados de
`PreflopStats` son idénticos antes y después del cambio. Paridad del adaptador
legado: **4.594 / 4.594**.

## 4. DIFERENCIAS DECLARADAS DEL CONTRATO ESTRICTO

Las siguientes cifras son de la ventana fiable de 877 manos (4.594 primeras
decisiones). El contrato estricto es el nuevo; la referencia es la etiqueta
histórica del entrenamiento.

| lectura | coincide | diferente | no resuelto |
|---|---:|---:|---:|
| estricto vs etiqueta histórica | 4.512 | 49 | 33 |
| `_preflop_spot` viejo vs estricto | 594 | 3.967 | 33 |
| `_preflop_raises` + limpe viejo vs `table_plan` | 4.384 | 208 | 2 |

### 4.1 Los 49 "diferentes" tienen una sola causa

No son 49 invenciones nuevas: son el efecto de que el contador legado cuenta
un limpe corto `b` como subida para el jugador siguiente.

| etiqueta histórica | lectura estricta | n |
|---|---|---:|
| `fold_vs_open` | `fold` | 14 |
| `call_open` | `call_limp` | 13 |
| `fold_vs_3bet` | `fold_vs_open` | 13 |
| `3bet` | `rol` | 4 |
| `call_3bet` | `call_open` | 3 |
| `squeeze` | `rol` | 2 |

### 4.2 Los 33 no resueltos

29 son `bb_check` históricos que en realidad son un `x` de una posición que no
es BB:

```
('bb_check', 'check_non_bb'): 29
motivo: check_fuera_de_BB
```

No se convierten a `bb_check` ni a `limp`. Quedan sin resolver, que es la
verdad del dato.

Los otros cuatro se concentran en `H_0357`: tras SB `p 0.5` y BB `p 1.0`, el
BB vuelve a aparecer con `b 0.5`. P0-2 declara esa acción como
`subida_sin_incremento`, `invalid`, con cuatro decisiones preflop dependientes.
La lectura estricta P0-1 ahora también la deja `unresolved` y tañe las
decisiones siguientes; no la vuelve a contar como una segunda ciega ni como un
limp corto. Las categorías históricas de esas cuatro decisiones quedan visibles
como unresolved, no se reatribuyen.

### 4.3 Las `b` de la ventana

| importe | n | lectura estricta |
|---|---:|---|
| `b > 1 BB` | 162 | 115 `open`, 44 `rol`, 2 ciega/post (no decisión), 1 unresolved (`H_0357`) |
| `b <= 1 BB` | 15 | 14 `limp` corto, 1 unresolved (`H_0357`) |

Total de `b` crudas: 177. Dos `b` >1 BB son posts del BB/no decisiones; el
`b 0.5` repetido de `H_0357` queda unresolved.

### 4.4 La lectura vieja del serving

`_preflop_spot` solo coincide con el contrato en **594 / 4.594** estados
(12,93 %). Las diferencias dominantes son:

| lectura vieja | lectura contextual | n |
|---|---|---:|
| `open` | `fold` | 1.533 |
| `open` | `fold_vs_open` | 1.068 |
| `3bet` | `open` | 275 |
| `call_open` | `limp` | 262 |
| `limp` | `bb_check` | 182 |
| `call_open` | `call_limp` | 159 |
| `3bet` | `rol` | 131 |
| `open` | `fold_vs_3bet` | 98 |
| `open` | `limp` | 91 |
| `open` | `rol` | 46 |

El patrón es el esperado: el parser viejo devuelve `open` por defecto para
folds, no distingue limpe de call y llama 3bet a cualquier `r`.

### 4.5 El estado de las tablas del héroe

`_preflop_raises` solo cuenta `'r'`; y `_recom_preflop` marca limpe solo con
`'c'` antes de un `'r'`. El contrato estricto cuenta las subidas reales y los
limpes cortos. Hay **208** estados de 4.594 con diferencia (4,53 %). Las
diferencias no son ruido: son aperturas `b` que el camino viejo no veía. Dos
prefijos de H_0357 quedan unresolved por la secuencia P0-2; están contabilizados
por separado, no como diferencias válidas de tabla.

Ejemplos de la tabla:

| viejo `(n_raises, limp, vs)` | nuevo `(n_raises, limp, vs)` | tablas nuevas | n |
|---|---|---|---:|
| `(0, False, '')` | `(1, False, 'UTG')` | `3B` / `Call_OR` | 65 |
| `(0, False, '')` | `(1, False, 'MP')` | `3B` / `Call_OR` | 51 |
| `(0, False, '')` | `(1, False, 'CO')` | `3B` / `Call_OR` | 23 |
| `(0, False, '')` | `(0, True, '')` | `ROL` | 19 |
| `(0, True, '')` | `(1, False, 'UTG')` | `3B` / `Call_OR` | 18 |

## 5. COBERTURA: LO QUE NO EXISTE SE DECLARA

El contrato no convierte una categoría sin celda en otra. Cada
`PreflopClassification` expone:

| `range_query_status` | significado |
|---|---|
| `available` | `ProfileRangeModel` tiene categoría de entrenamiento |
| `no_range` | fold/check: no hay rango que muestrear |
| `no_table` | categoría válida sin celda (5bet, call_4bet, fold_vs_4bet, ...) |
| `unresolved` | la secuencia no se pudo leer |

En la ventana tras añadir la propagación explícita de `H_0357`:
`available=1680`, `no_range=2881`, `unresolved=33`,
`no_table=0` (las 5bet+ no aparecen como primera decisión en esas 877).

Además, `ProfileRangeModel.CAT_TABLE` no tiene celdas para `5bet`,
`call_4bet`, `fold_vs_4bet`, `bb_check` ni `check_non_bb`; y sus claves
`limp`/`call_limp` apuntan al prefijo `LIMP`, cuyas tablas no están en
`data/preflop_matrices.json`. Esto **no se corrige aquí**: se registra como
ausencia. La activación del contrato tendrá que decidir qué hacer con esas
categorías antes de consultar el modelo de rangos.

## 6. MODO SOMBRA

### 6.1 Puntos de instrumentación

| consumidor | dónde |
|---|---|
| rango del rival principal de la sombra | `Asistente._rango_main` |
| rango inicial del rival en producción | `Asistente._recomendacion_para` |
| tablas preflop del héroe | `Asistente._recom_preflop` |

Cada registro contiene:

- `old`: lectura vieja y `vs_pos`;
- `new`: spot, acción, categoría de entrenamiento, estado, motivo,
  `range_query_status`, contexto completo y clasificación cruda;
- `legacy_training`: qué habría dicho el entrenamiento histórico;
- `consumer`, `hand_id`, `player_pos`, secuencia;
- `difference`, `difference_fields`, `unresolved`.

### 6.2 Dónde se escribe

`ShadowPreflopLog` guarda en memoria por defecto (`path=None`). **No toca
`data/`**. Para persistir una sesión:

```powershell
$env:POKER_PREFLOP_SHADOW_LOG = "data/shadow_preflop.jsonl"
```

Ese fichero está ignorado por git. La suite no lo escribe.

### 6.3 Prueba de que la sombra no cambia la recomendación

`motor/test_preflop_contract.py::test_sombra_no_cambia_la_recomendacion_preflop`
ejecuta `_recom_preflop` con el log desactivado y con el log activo, misma
semilla, y compara:

- `evs.ev`
- `evs.chosen`
- `evs.candidate_actions`

El resultado es idéntico. El registro de sombra se llena, pero no participa en
ninguna decisión.

## 7. PRUEBAS

Ejecutado:

```powershell
python -m pytest motor/test_learn.py motor/test_asistente_live.py `
  motor/test_player_ranges.py motor/test_postflop_ranges.py `
  motor/test_preflop.py motor/test_preflop_cobertura.py `
  motor/test_observations.py motor/test_contratos_pending.py `
  motor/test_preflop_contract.py -q
```

Resultado histórico de P0-1: **227 passed, 1 xfailed**. La regresión adicional
de H_0357 se prueba en P0-6 y las cifras actuales se actualizan en esta sección.

No se afirma suite completa verde. Los censos históricos de
`test_auditar_origen.py`, `test_cm004.py` y el conteo de postas de
`test_accion_p.py` siguen fijando la base anterior (1253 manos / 2522 `p`) y
hoy fallan contra la base canónica de 1344. Son deudas previas, fuera de P0-1;
no se han tocado ni se han usado para declarar este cambio verde.

El `xfail` es deliberado y estricto:

- `test_xfail_paridad_serving_viejo_877` comprueba que el serving viejo
  **todavía no** coincide con el contrato. Falla hoy (xfail) y, cuando se
  active el contrato, pasará a XPASS y romperá el test para obligar a
  actualizarlo.

La prueba que fija la deuda estricta es
`test_deuda_legada_y_restricciones_p02_quedan_visibles`; la de las
ciegas, `test_las_162_b_mayor_1bb_y_las_15_b_menor_igual_1bb`.

## 8. REPRODUCIR LAS CIFRAS

```powershell
python tools/auditar_contrato_preflop.py
python tools/auditar_contrato_preflop.py --json
```

El script solo lee la base y no escribe logs ni derivatives.

## 9. QUÉ NO SE HA HECHO

- No se ha activado el contrato en las recomendaciones.
- No se ha cambiado `data/`, ni derivados, hashes, manifests, pines, rangos,
  probabilidades, priors, tablas, la selección de 877 ni `MULTIWAY_SOPORTADO`.
- P0-2 sigue en sombra; no se ha empezado B2, sesiones reales ni calibración.
- No se ha cambiado la etiqueta PEZ/TIBURON.

La activación y cualquier trabajo posterior quedan a la espera de
autorización explícita.
