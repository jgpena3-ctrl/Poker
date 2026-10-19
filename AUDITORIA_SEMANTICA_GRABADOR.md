# AUDITORÍA SEMÁNTICA DEL GRABADOR

> ## Parte II — plan de actuación
>
> Debajo de la Parte I (§ 1-9) está la **PARTE II**, que convierte los hallazgos
> en decisiones ejecutables: clasificación por ventana, búsqueda del grabador
> histórico, esquema de captura futuro, plan de pruebas y vía recomendada.
>
> **Resultado principal de la Parte II:** el grabador histórico **sí se ha
> recuperado parcialmente** (1280 blobs colgantes, versiones fechadas por la
> cabecera de los `.pyc`), y la semántica de `amount` **cambió dentro del
> periodo capturado**: de `delta + acumulado` a `delta` puro, con el corte entre
> el 11 y el 20 de septiembre. **922 manos quedan con semántica confirmada y 336
> quedan condicionales.**

**Objeto:** `data/hands_db.jsonl` (1258 manos, 13826 acciones) y el código que
la produjo.
**Fecha del análisis:** sobre `HEAD 6b7f199`.
**SHA-256 de la base, antes y después:**
`35727961646dfaba2c67fd5ee0dbe9b0669d3156f9c6f3fa3585060a93f097e2` — **sin cambios**.

Este informe **retira conclusiones** del informe anterior. No las reformula: las
marca como no sustainable y explica por qué.

| marca | significado |
|---|---|
| **[C]** | hecho comprobado en el código o reproducible con los datos |
| **[O]** | anomalía observada: patrón medido, causa no determinada |
| **[I]** | inferencia compatible con los datos, que podría ser otra cosa |
| **[D]** | decisión de diseño, no una conclusión empírica |
| **[P]** | pendiente: falta el dato que lo resuelve |

---

## 1. Resumen ejecutivo

**1.1 — El informe anterior atribuyó la mezcla a dos grabadores. Eso es falso.**

**[C]** El hallazgo de que `record_hand.py` no escribe el campo `allin` y
`recorder_live.py` sí, es cierto. Pero la inferencia que se hizo —«las 73 manos
sin `allin` las escribió `record_hand.py`»— **se refuta con dos hechos**:

- **[C]** `record_hand.py` nunca escribió `winner` en ninguna versión
  (`git log -S"winner" -- recorder/record_hand.py` solo encuentra la coincidencia
  con `showdown.winner1`). Pero **`winner` está en 1258 de 1258 manos**. Si
  hubieran sido las 73, no lo tendrían.
- **[C]** El commit inicial del repositorio es **`b97349e`, fechado 2026-08-12
  13:29:13 -0500**. Las 73 manos sin `allin` están fechadas el **2026-07-27 y
  2026-07-28**: **anteriores al repositorio**.

**[C]** La grupo sin `allin` es un **subconjunto estricto** de las manos
capturadas antes del snapshot. No son «dos grabadores», son **dos poblaciones
temporales**, y el código de una de ellas **no está en el repositorio**.

**1.2 — La frontera que importa no es `allin`, es la fecha.**

| grupo | manos | fechas | `allin` | código en el repo |
|---|---:|---|---|---|
| **A** — sin campo `allin` | 73 | 2026-07-27 → 07-28 | ausente | **no** |
| **B** — antes del snapshot | 263 | 2026-07-29 → 08-09 | presente | **no** |
| **C** — snapshot o posterior | 922 | 2026-08-12 → 09-18 | presente | sí, con reservas |

**[C]** **336 manos (26,7 %)** las capturó código ausente del repositorio. Para
ellas, la semántica de `amount` **no es determinable con lo que hay aquí**.
Por eso este informe agrupa por A/B/C y no da cifras de la base entera como si
fueran homogéneas.

**1.3 — `amount` tiene cuatro orígenes demostrables, no uno.**

El informe anterior identificaba solo dos semánticas. Hay **cuatro** ramas de escritura,
y la dominante es un **delta de stack**, no una caja:

| grabador | rama | `amount` es |
|---|---|---|
| `record_hand.py` | 4 ramas | la **caja** del jugador, leída en el fotograma de detección |
| `recorder_live.py` | `_reconstruct_preflop` (497-557) | el **nivel absoluto** de la caja, leído de un snapshot |
| `recorder_live.py` | `_detect_deltas` normal (698-714) | el **delta del stack** `prev_stake − cur_stake`, redondeado |
| `recorder_live.py` | `_detect_deltas` all-in (669-685) | `prev_stake + prev_bet` |

**1.4 — El clasificador compara deltas contra niveles. Eso explica el «patrón de
1.0» del BB sin necesidad de culpar al ROI.**

**[C]** `apuesta_viva()` acumula la viva con `max(viva, amount)` y `calls_por_debajo()`
marca como corta toda `c` con `amount < viva`. Si `amount` es un delta, comparar
un incremento contra un nivel no significa nada.

**[C]** Y hay un caso concreto y exacto: **el BB ya tiene 1.0 de ciega en la
caja**. Si su call es un delta, el incremento es `viva − 1.0`, y `falta` vale
**exactamente 1.0**. Eso es una call correcta, no un error de lectura.

Medido sobre el grupo C:

| | valor |
|---|---:|
| calls del grupo C | 1915 |
| calls marcadas como cortas por `calls_por_debajo` | 400 (20.9 %) |
| de esas, con `falta == 1.0` exacto | 288 (72.0 %) |
| de esas 288, con aportación previa ≈ 1.0 | **286 (99.3 %)** |

**[C]** La relación es mecánica. El BB aparece con 60.0 % de calls «cortas»
contra 5.6–21.2 % del resto, y el BB es **el único que siempre tiene 1.0 en la
caja**.

**Lo que el informe anterior afirmaba sobre esto queda retirado**: «el BB tiene
un patrón propio de 1.0 por debajo que no es del ROI» era una hipótesis
compatible con los datos. Los datos dicen otra cosa: es el resultado esperado de
comparar un delta contra un nivel. La investigación del ROI perseguía un
fantasma.

**1.5 — `amount == stack` no es una firma de all-in.**

**[C]** `players[].stack` se fija **una vez**, al abrir la mano, como
`(stake + bet)` — el stack inicial **más la ciega ya posteada**. `amount` puede
ser un delta, un nivel o un `prev_stake + prev_bet`. No son magnitudes
comparables.

**[C]** Sobre 263 acciones de jugadores con all-in declarado:

| | n | `amount == stack` | `amount > stack` | `amount < stack` |
|---|---:|---:|---:|---:|
| grupo B | 63 | 4 | **0** | 59 |
| grupo C | 200 | 14 | **0** | 186 |
| **total** | **263** | **18 (6.8 %)** | **0** | **245** |

**[D]** La regla de «all-in corto» del clasificador, que se apoya en
`amount ≈ stack`, no tiene base dimensional. Las 18 coincidencias son
**compatibles**, no evidencia.

**1.6 — Los tres conteos son aritméticamente coherentes y semánticamente vacíos.**

**[C]** 5433 + 445 + 96 = 5974 = 2398 + 2558 + 1018. Cuadran.

**[C]** Pero cada una de las tres reglas que los producen compara magnitudes que
no son comparables (§ 3). **[D]** «CALCULABLE» no significa que la aportación sea
reconstruible. **La cifra debe retirarse de toda presentación como aportación
válida** hasta rehacer el diagnóstico sobre la semántica del delta.

**1.7 — El esquema no conserva la procedencia de las acciones.**

**[C]** Los únicos campos que existen en una acción del JSONL son `pos`,
`action`, `amount` y, en 23 casos, `inferred`.

**[C]** El código actual escribe además **`amount_type`** (`'observed'` /
`'delta'`) y **lanza `ValueError` sin él** (`recorder_live.py:581-584`). Ese
campo existe en el código desde `8bd55be`, posterior al snapshot.

**[C]** **`amount_type` no aparece en ninguna de las 13826 acciones.** El
contrato que el código actual impone no se aplicó nunca a estos datos. **El
código del repositorio no puede usarse para determinar la semántica del `amount`
grabado**: es más nuevo que la base.

---

## 2. Semántica demostrada de `amount` por rama

### 2.1 `record_hand.py` — 404 líneas, cuatro ramas de escritura

| rama | línea | expresión | magnitud | referencia temporal | redondeo | limitaciones |
|---|---|---|---|---|---|---|
| ciegas iniciales | 209 | `amount: bet` donde `bet = state[pid_bet]` | caja del jugador | fotograma de apertura de mano | ninguno | se registra **lo que ya había** al abrir la mano, sin saber si la ciega se captó |
| fold | 239, 268 | `amount: 0.0` literal | **constante** | — | — | no es una lectura |
| bet/call por delta de caja | 248 | `amount: new_bet` | caja **nueva**, acumulada en la calle | fotograma de detección | ninguno | puede ser de un fotograma anterior al del movimiento real |
| raise por delta de caja | 251 | `amount: new_bet` | caja acumulada | fotograma de detección | ninguno | `new_bet > old_bet and old_bet > 0`: **un cambio desde 0.0 no se detecta** |
| fallback por etiqueta de estado | 273, 278, 284 | `amount: state[pid_bet] or 0` | caja, o **0.0 si falla** | fotograma actual | ninguno | **evidencia de grado distinto**: no es un delta, es una etiqueta |

**[C]** En las cinco ramas `amount` es **la caja**, nunca un delta. La caja del
felt es **acumulada dentro de la calle**.

**[C]** Las ramas 3 y 4 son detectadas por diferencia; la rama 5 es **inferida de
una etiqueta**. No llevan ninguna marca que las distinga en el JSONL.

**[C]** `0.0 → X` no emite acción (rama 4 exige `old_bet > 0`), pero
`None → 0.0` **sí emite**, con importe 0.0. Y `or 0` convierte una lectura
ausente en un cero indistinguible de un check.

**[C]** Este grabador **no puede emitir `x`** (su `STATE_ACTIONS` no lo tiene) y
**no escribe `allin` ni `winner`**. Ninguna mano de la base cumple las dos
condiciones. **[D]** Por tanto **`record_hand.py` no produjo ninguna mano de
`data/hands_db.jsonl`**, o produjo manos que no están en este fichero.

### 2.2 `recorder_live.py` — ramas de escritura

| rama | línea | expresión | magnitud | referencia temporal | redondeo | limitaciones |
|---|---|---|---|---|---|---|
| **preflop reconstruido** | 497-557 | `amt = round(bet, 2)` con `bet = state[pid_bet]` | **nivel absoluto** de la caja | **un único snapshot** al abrir la mano | `round(...,2)` y umbral `+0.15` | el orden es **inferido por posición**, no observado |
| normal (dinero) | 699-711 | `delta = prev_stake − cur_stake`; `amt = _round_bet(delta, run_max)` | **delta del stack** | entre `last_state` y `state` | `_round_bet` **falsea a la viva** si \|d−max\|≤0.1 | requiere `delta > 0.05`; el orden es el de `ORDER`, no el del frame |
| all-in | 670-684 | `amt = prev_stake + prev_bet` | stack **antes** + caja | frame del all-in | `round(...,2)` | ya lleva la apuesta dentro: no es comparable con `stack` |
| fold | 506, 693 | `amount: 0.0` | constante | — | — | — |
| **fusión en el cierre de calle** | 845-852 | `merged[-1]['amount'] += a['amount']` | **suma de deltas = nivel** | al cerrar la calle | `round(...,2)` | **destruye acciones separadas** y convierte deltas en niveles |
| **checks implícitos** | 995 | `{'pos','action':'x','amount':0.0}` | **cero por construcción** | — | — | **sin marca de inferencia**; inserta en `existing[0:0]` y **borra** checks en 983-985 |

**[C] `amount` no tiene una semántica por grabador: tiene una por rama, y dentro
de `recorder_live` la rama normal y la de all-in miden cosas distintas.** Por eso
no se puede extender una conclusión de una rama a otra sin demostrarlo.

### 2.3 Lo que las ramas **no** resuelven

- **[P]** Cuál era la versión de `recorder_live.py` en cada momento de captura.
  El código tiene 11 commits, el primero de 2026-08-12, y las manos llegan hasta
  2026-09-18. **No hay marca de versión en el JSONL.**
- **[P]** Qué semántica tenía `amount` en las 336 manos anteriores al snapshot.
- **[C]** `_round_bet` (136-146) puede **convertir un importe en otro**: si
  \|importe − viva\| ∈ (0, 0.1] devuelve la viva. Conviviendo con
  `if delta > 0.05`, la ventana muerta es 0.05 < delta ≤ 0.1 aproximadamente.
- **[C]** `_detect_river_check` (750-772) calcula la señal de «dos fotogramas
  idénticos» y **no la transmite**: llama a
  `_add_implied_checks('river', state)` **sin `confirm_all_check=True`**. Su
  docstring dice «se registran los checks que falten»; con la firma actual de
  `_add_implied_checks`, sin apostadores registrados no se registra ninguno.
  **Defecto de implementación demostrado.**

---

## 3. Matriz de validez del clasificador

Reglas de `tools/diagnostico_grabador.py`, contra la semántica real.

| regla | código | grupo A | grupo B | grupo C (`recorder_live`, mayoritario) | veredicto |
|---|---|---|---|---|---|
| acumular viva con `max(viva, amount)` | 95-96 | **Válida**: `amount` es caja acumulada | **Válida**: nivel | **Inválida**: con un delta, una subida deja la viva por debajo del nivel real | **Inválida en C** |
| «`amount >= viva` → alcanza la viva» | 133 | Válida | Válida | **Condicional**: válida para una primera call sin aportación previa; **falsa** si el jugador ya tiene parte de la calle | **Condicional** |
| «`amount > viva` → sospechosa» | 309-317 | Válida (caja no baja) | Válida | **Inválida**: una subida produce un delta que supera la viva legítimamente | **Inválida en C** |
| «importe descendente → sospechoso» | 297-306 | Válida (caja acumulada) | **Inválida** (nivel absoluto) | **Inválida**: dos deltas independientes **deben** poder bajar | **Inválida en B y C** |
| `importe − caja_previa` como aportación | 322-326 | Válida | **Inválida** | **Inválida**: restar niveles de deltas | **Inválida en B y C** |
| acción repetida (misma clave) | 309 | Válida como sospecha | Válida | **Válida como sospecha**, pero `_finalize_street` ya fusiona `c`/`b` consecutivos, así que lo que sobrevive no es «no fusionable» por diseño | **Válida con matiz** |
| `amount == 0.0` → check | 331-336 | **Condicional**: `record_hand` emite `c 0.0` por `pasar` | Condicional | **Condicional**: los `x` son inventados, los `c 0.0` no deberían existir | **Condicional** |
| `amount ≈ stack` → all-in corto | 327-334 | **Inválida**: caja vs stack al abrir | **Inválida** | **Inválida**: sin homogeneidad dimensional; se cumple 6.8 % | **Inválida** |
| `c` sin acción previa → INDETERMINADA | 337-341 | Válida | Válida | **Condicional**: válida si la aportación previa no se registró | **Condicional** |
| `or 0.0` para `amount` ausente | 290 | **Inválida**: `None`→0.0 | Inválida | Inválida | **Inválida en todos** |

### 3.1 Qué sobrevive y qué no

**[C]** Sobre el **grupo C**, que es el 73 % de la base, de las diez reglas
**ninguna** es válida sin condiciones. Las dos que quedan condicionales
(`amount >= viva`, `c` sin previa) dependen de que la aportación previa esté
completa, y eso no se puede comprobar.

**[C]** Consecuencia directa: **el reparto 5433 / 445 / 96 no es un reparto entre
aportaciones válidas y aportaciones dudosas.** Es un reparto entre
comportamientos de un clasificador al que se le han pedido preguntas que la
magnitud no puede responder.

**[D]** No se corrige aquí. Retirar las cifras y rehacer el diagnóstico sobre la
semántica del delta es un trabajo distinto, con su propia decisión de diseño
(§ 8).

### 3.2 Reproducción por grupo, con denominadores

**[C]** Las 498 calls cortas **sí se reproducen** con la regla escrita, y se
descomponen en dos poblaciones distintas:

| grupo | calls | cortas | % cortas | de ellas `falta == 1.0` | de esas, con previa ≈1.0 |
|---|---:|---:|---:|---:|---:|
| A (73) | 140 | 23 | 16.4 % | 10 (43.5 %) | 3 (30.0 %) |
| B (263) | 503 | 75 | 14.9 % | 39 (52.0 %) | **0 (0.0 %)** |
| C (922) | 1915 | 400 | 20.9 % | 288 (72.0 %) | **286 (99.3 %)** |
| **total** | **2558** | **498** | 19.5 % | 337 | 289 |

**[C]** La cifra agregada **oculta dos fenómenos distintos**: en C el 99.3 % de
las faltas de 1.0 tiene explicación mecánica; en B **ninguna** la tiene. La
cifra 498 no debe usarse como un solo hecho.

**[C]** Por posición, grupo C:

| posición | calls | cortas | % |
|---|---:|---:|---:|
| **BB** | 335 | **201** | **60.0 %** |
| SB | 414 | 23 | 5.6 % |
| UTG | 226 | 48 | 21.2 % |
| MP | 318 | 54 | 17.0 % |
| CO | 313 | 45 | 14.4 % |
| BTN | 309 | 29 | 9.4 % |

**[I]** El BB destaca porque es el único con una aportación previa garantizada de
1.0. **[P]** En los grupos A y B el BB también destaca (50.0 % y 44.0 %) pero
**sin** aportación previa detectable, lo que indica otro mecanismo o un esquema
distinto. No se puede determinar con este código.

---

## 4. Procedencia y significado de `allin` y `stack`

### 4.1 Cómo se genera `allin`

**[C]** `recorder_live.py:1040-1042`:

```python
out['allin'] = [p['_id'] for p in self.hand['players']
                if p['_id'] in self._allin_players and p['active']
                and p['pos'] not in self._folded_positions]
```

**[C]** `_allin_players` se rellena en **un solo sitio**, la 681, dentro de la
rama de all-in de `_detect_deltas`, cuya condición es
`was_active and cur_stake is None and not dimmed` (669). **`cur_stake is None`
significa que el stack dejó de ser legible**, que es la señal que el grabador
usa para el all-in, no una comparación con el importe.

**[C]** La lista **filtra por `active`** y por `not in _folded_positions`. Eso es
la corrección de INC-002 / `H_0851`: un jugador que se compromete y luego foldea
**no** sale en `allin`. El propio comentario (1034-1039) dice que las manos ya
grabadas **no se tocaron**.

**Sobre `dimmed` (665):** `cur_st in ('retirarse','ausente','inactivo','sin jugador','fuera')`.
Sirve para **no** confundir «el stack desapareció porque foldeó» con «el stack
desapareció porque se fue». Es una heurística de OCR sobre texto de estado.

### 4.2 ¿Cuándo pasa un stack a `None`?

**[P]** No se puede determinar desde el código. `None` significa «la ROI del stack
no leyó nada»: puede ser un all-in, un fold, un jugador difuminado, o un fallo de
OCR. El grabador **desambigua con `dimmed`**, que es un segundo OCR. Los dos
pueden fallar por separado.

### 4.3 `stack`

**[C]** Se fija **una sola vez**, en `start_hand`:

- `record_hand.py:181` — `stack = state[f'{pid}_stake']`
- `recorder_live.py:358` — `stack = (stake + bet) if ambos no None else stake`

**[C]** Es, por tanto, **el stack en el instante de abrir la mano, más la ciega
ya posteada**. No es el stack restante, ni el anterior, ni el de cierre. **No se
actualiza nunca durante la mano.**

**[C]** La comparación `amount == stack` es entre un delta (o un nivel de caja) y
un stack inicial con ciega incluida. DimENSIONalmente no homogénea. Se cumple
en 18 de 263 acciones de all-in (6.8 %) y **nunca** por exceso.

### 4.4 ¿Es `allin` un discriminante fiable de procedencia?

**[C]** **No.** Lo que sí demuestra:

- `record_hand.py` nunca escribió `allin` **ni** `winner`.
- `winner` está en **1258/1258** manos.
- **⇒ `allin` ausente no puede significa «lo escribió `record_hand.py`».**
- **[C]** Las 73 son las **más antiguas** (07-27/28), anteriores al snapshot
  (2026-08-12), y son un **subconjunto estricto** de las 336 pre-snapshot.

**[D]** `allin` ausente marca una **frontera de versión**, no un programa: un
subconjunto de un grupo más grande. **No es coextensiva con ninguna población de
código.**

### 4.5 Clasificación del all-in según la evidencia

| categoría | definición | cantidad medida |
|---|---|---:|
| **All-in declarado** | el grabador lo escribió en `allin` | **201 manos** (B 40, C 161) |
| **All-in compatible** | `amount == stack` dentro de ±0.05 | 18 acciones (6.8 % de las de jugadores con all-in) |
| **All-in inferido por combinación** | `amount ≈ stack` sin declaración | **no se sostiene**: la comparación carece de homogeneidad |
| **All-in no determinable** | el resto | mayoría |

**[D]** Un `amount == stack` **no debe convertirse en all-in confirmado**. En el
informe anterior se contaron 38 «compromisos reconstruidos que coinciden con el
stack» y se lea como validación. No lo es.

---

## 5. Qué es aportación calculada y qué es acción detectada

### 5.1 Lo que el esquema conserva

**[C]** Campos de una acción en el JSONL: `pos`, `action`, `amount`, e
`inferred` en 23 casos. Nada más.

**[C]** Los 23 `inferred: True` los inyectó `tools/aplicar_correcciones.py`
(`CHECK_INFERIDO`, línea 76-77): checks de BB **fabricados por post-proceso** en
23 manos. Están marcados, lo cual es una suerte excepcional; los que fabricó el
grabador **no lo están**.

### 5.2 Lo que el esquema pierde

| lo que se pierde | dónde | efecto |
|---|---|---|
| `amount_type` (`observed`/`delta`) | `_add_action` lo escribe; el JSONL no lo tiene | **la distinción que hace falta para todo lo demás** |
| marca de inferencia en `x` | `_add_implied_checks:995` escribe `x` sin marca | un check inventado es indistinguible de uno observado |
| marca de inferencia en `c` de fallback | `record_hand.py:284` | idem |
| orden observado | `_order_actions` (857-927) reescribe la lista | el orden del JSONL es **reconstruido**, no observado |
| fotogramas y marcas de tiempo | no se registran | no se puede separar un eco de una lectura |
|Actions fusionadas | `_finalize_street:845-852` | dos `c`/`b` del mismo jugador se **suman en una** |
| `x` insertados | `_add_implied_checks:997` | se añaden acciones nuevas al JSONL |
| `x` borrados | `_add_implied_checks:983-985` | se eliminan acciones que sí se habían grabado |
| stack por fotograma | `players[].stack` es único y estático | no hay forma de validar un delta contra nada |

### 5.3 Las siete categorías que pedía distinguir

| categoría | ¿el esquema la distingue? | cómo se identifica en los datos |
|---|---|---|
| 1. acción registrada | sí | cualquier entrada |
| 2. detectada por cambio de estado | **no** | nada en el JSONL |
| 3. inferida por regla | **parcial**: solo 23 de miles | `inferred: True` |
| 4. posiblemente repetida | sí, indirectamente | dos entradas con la misma clave `(pos, action, amount)` |
| 5. aportación reconstruible | **no** | requiere conocer la semántica, que no está |
| 6. importe compatible con una interpretación | no | requiere información externa |
| 7. existencia o importe no determinable | — | es la categoría mayoritaria |

**[D]** **La limitación es estructural y no se arregla con más análisis del
JSONL.** Para distinguir la 2 de la 3 falta un campo que el grabador no escribe.
La única salida realista es **capturar manos nuevas con el código actual**, que
ya escribe `amount_type`, y comparar.

---

## 6. Auditoría de las pruebas

### 6.1 Clasificación

**Pruebas de caracterización** — fijan el comportamiento actual, incluidas las
que documentan defectos. **No son evidencia de que el clasificador sea correcto.**

| prueba | qué fija | nature |
|---|---|---|
| `test_un_allin_corto_es_calculable` | repetición + stack → `CALCULABLE` | caracterización de un **defecto** |
| `test_allin_con_accion_repetida_sale_calculable` | `CALCULABLE` con aporte 0.0 | **defecto** |
| `test_allin_con_caja_incoherente_sale_calculable` | `CALCULABLE` con **aporte −5.0** | **defecto grave** |
| `test_importe_ausente_se_confunde_con_cero` | ausente → 0.0 + motivo inventado | **defecto** |
| `test_importe_none_tambien_se_confunde` | `None` → 0.0 | **defecto** |
| `test_una_caja_que_baixa_es_sospechosa` | delta descendente → sospechoso | **defecto en el modelo** |

**Pruebas de validez semántica** — demuestran una propiedad necesaria del
diagnóstico:

| prueba | propiedad | estado |
|---|---|---|
| `test_la_base_son_dos_grabadores` | dos poblaciones | **el nombre es falso**: no son dos grabadores (§ 1.1) |
| `test_el_campo_allin_no_lo_escribe_record_hand` | `allin` ausente ≠ `record_hand` | **contradice** la prueba anterior |
| `test_el_allin_no_esta_confirmado` | `amount == stack` no prueba all-in | válida |
| `test_la_apertura_no_tiene_la_misma_forma_en_los_dos` | distribuciones distintas | válida, pero **grupo incorrecto** |
| `test_el_importe_emito_es_la_caja_nueva` | `record_hand` emite caja | válida **solo para A/B**, que no existen |

### 6.2 Contradicción entre pruebas

**[C]** `test_la_base_son_dos_grabadores` afirma que las 73 sin `allin` son de
`record_hand.py`. `test_el_campo_allin_no_lo_escribe_record_hand` afirma que esa
ausencia **no** identifica al grabador. **Las dos se contradicen y ambas pasan**,
porque la segunda solo comprueba el código, no los datos. Ninguna detectó el
error; las dos lo fijaron.

### 6.3 Pruebas tautológicas

**[C]** Estas recalculan la misma cifra con la misma regla y la comparan con una
constante. **No validan nada**, solo fijan el número:

- `test_la_clasificacion_sobre_la_base` — 5433 / 445 / 96
- `test_el_desglose_por_accion_por_resultado_es_coherente` — la matriz 2D
- `test_las_498_no_las_503` — recalcula 498
- `test_las_repeticiones_no_son_consecutivas` — recalcula 26
- `test_la_base_son_dos_grabadores` — recalcula 1185 / 73

**[C]** La coherencia aritmética de una matriz que suma 5974 **demuestra que la
matriz es internamente consistente, no que las aportaciones sean válidas.**

### 6.4 La regresión de procedencia es frágil

**[C]** `test_la_base_son_dos_grabadores` verifica los números 1185 y 73 y que
las ids son `H_0001..H_0073`. Si se **añadiera una mano** a la base, la prueba
fallaría **sin que hubiera cambiado la procedencia de nada**. Es una comprobación
de **estructura**, no de procedencia, y se presenta como lo segundo.

**[C]** Lo mismo en `test_la_apertura_no_tiene_la_misma_forma_en_los_dos`, que
compara diccionarios exactos.

### 6.5 Las pruebas sintéticas modelan la rama equivocada

**[C]** Todas las pruebas de `detect_actions` construyen un `HandRecorder` de
`record_hand.py`, cuya `amount` es **caja acumulada**. **[C]** Pero ninguna mano
de la base procede de `record_hand.py` (§ 4.4). **Modelan el 0 % de los datos.**

**[C]** Los dos casos de all-in sintéticos también: reproducen una rama que el
grabador real no usa, porque el `amount` de la rama de all-in real es
`prev_stake + prev_bet` y el del stack es un inicial con ciega.

### 6.6 Lo que ninguna prueba cubre

- Que la semántica de `amount` sea la que dice el modelo. **[C]** Ninguna prueba
  puede hacerlo: el JSONL no lleva `amount_type`.
- Que la viala de `apuesta_viva` sea correcta para deltas.
- Que `apuesta_viva` mantenga la correspondencia de índices. **[C]** Sí la
  mantiene: `eventos` guarda `i` como el índice original (línea 93), y
  `calls_por_debajo` indexa con `ev['i']` sobre la lista completa. **Pero** una
  acción con importe ilegible hace `continue` (91-92) y **no avanza la viva**: si
  la acción descartada era una `b` o `r`, **todas las posteriores se comparan
  contra una viva demasiado baja**.

---

## 7. Limitaciones del esquema y evidencia que falta

### 7.1 Lo que no se puede determinar con este código y estos datos

| pregunta | por qué no |
|---|---|
| semántica de `amount` de las 336 manos pre-snapshot | el código no está en el repo |
| versión del grabador en cada captura | no hay marca de versión en el JSONL |
| si una acción fue detectada o inferida | no hay marca de procedencia |
| si un `c 0.0` es un check real | `record_hand` mapea `pasar → c`; `_add_implied_checks` escribe `x` |
| si un `x` se vio o se fabricó | sin marca |
| orden real de actuación | `_order_actions` lo reescribe |
| por qué un stack pasa a `None` | `None` significa «OCR no leyó», con 4 causas posibles |
| si un `c` corto es un error de OCR o una call correcta | depende de la aportación previa, que no se sabe si está completa |

### 7.2 Evidencia externa que desbloquearía cada punto

| evidencia | qué desbloquea |
|---|---|
| **capturas nuevas con el código actual** (que ya escribe `amount_type`) | la distinción observado/delta, que es la clave de todo lo demás |
| una captura del BB con su caja, en el momento de la call | si el «falta 1.0» era OCR o geometría de la caja |
| el código del grabador en las fechas 07-27 → 08-12 | la semántica de las 336 manos |
| el log del OCR: qué ROI leyó qué y cuándo | distinguir `None` por all-in, fold o fallo |
| `H_0039` y cualquier mano con eco: fotogramas | distinguir una lectura obsoleta de dos acciones |

---

## 8. Plan de acción

### 8.1 Tabla de decisión

| hallazgo | evidencia | métrica afectada | corrección posible | riesgo de cambiarla | requiere evidencia externa |
|---|---|---|---|---|---|
| **`amount` es un delta en la rama mayoritaria** | **[C]** `recorder_live.py:699` | todas | redefinir el clasificador sobre deltas | **alto**: cambia los tres conteos | no |
| **viva por `max()` sobre deltas** | **[C]** `diagnostico_grabador.py:95` | 498, %BB | acumular niveles reconstruidos | alto | no |
| **el «falta 1.0» del BB es mecánico** | **[C]** 286/288 con previa ≈1.0 | § 8 del informe previo | **retirar la hipótesis del ROI** | **bajo**: es una retirada | no |
| **336 manos sin código conocido** | **[C]** fechas < 2026-08-12 | cualquier métrica agregada | segmentar por grupo | medio | **sí**: el código de esas fechas |
| **`amount_type` ausente en los datos** | **[C]** 0/13826 | confianza en toda la semántica | capturar de nuevo | — | **sí**: capturas nuevas |
| **checks inventados sin marca** | **[C]** `_add_implied_checks:995` | `x`, acciones totales | añadir marca | bajo (solo a futuro) | no |
| **`_detect_river_check` no propaga la confirmación** | **[C]** 772 vs la firma | `x` en river | pasar `confirm_all_check=True` | medio: más checks | no |
| **`amount == stack` no es firma de all-in** | **[C]** 18/263 | «all-ins cortos» | retirar el uso | bajo | no |
| **fusión de `c`/`b` consecutivos** | **[C]** 845-852 | nº de acciones, repeticiones | nada que hacer; documentar | — | no |
| **`_round_bet` falsea a la viva** | **[C]** 136-146 | 0.05–0.1 de ventana muerta | documentar | bajo | no |
| **5433/445/96 sin base semántica** | **[C]** § 3 | los tres conteos | **retirar** | **bajo**: es una retirada | no |
| **`inferred` en 23 acciones** | **[C]** `aplicar_correcciones.py:76` | 23 acciones BB | ya está marcado | — | no |

### 8.2 Orden

**P0 — retiradas, sin tocar código (riesgo nulo, valor alto):**

1. Retirar del informe la afirmación «dos grabadores». Sustituir por la
   segmentación A/B/C.
2. Retirar «el BB tiene un patrón de 1.0 que no es del ROI». Explicado por la
   comparación delta/nivel.
3. Retirar `amount == stack` como evidencia de all-in. Citar 18/263.
4. Marcar 5433 / 445 / 96 como **aritméticamente coherentes y semánticamente
   vacíos**.
5. Corregir las dos pruebas que se contradicen, o retirar la afirmación de
   «dos grabadores».

**P1 — con evidencia externa:**

6. Localizar el grabador de 2026-07-27 → 08-12. Sin eso, 336 manos quedan sin
   semiántica declarada.
7. Capturar manos nuevas con el código actual, que ya escribe `amount_type`.
   Es la única vía para cerrar la cadena.

**P2 — decidible sin evidencia externa:**

8. Corregir `_detect_river_check` para que propague `confirm_all_check`.
9. Marcar con `inferred: True` los checks que fabrica `_add_implied_checks`.
10. **Decidir** si `clasificar_aportado` se reescribe sobre deltas o se retira.
    Esta decisión cambia los conteos y no se toma aquí.

**[P]** Nada de P2 es urgente: **ninguna de esas correcciones cambia lo que ya
está grabado**, y P1 es lo que bloquea cualquier métrica fiable.

---

## 9. Verificación de integridad y pruebas

### 9.1 Integridad de la base

**[M]** SHA-256 de `data/hands_db.jsonl`, **antes de empezar**:

```
35727961646dfaba2c67fd5ee0dbe9b0669d3156f9c6f3fa3585060a93f097e2
```

**[M]** SHA-256 **al terminar**: **idéntico**.

**[M]** 1 782 206 bytes · 1258 líneas, sin cambios.

**[M]** `git status` al empezar: limpio, `HEAD 6b7f199`. Los cambios de la
sesión anterior ya estaban commiteados y el merge los conservó.

### 9.2 Archivos modificados

| archivo | modificación | por qué |
|---|---|---|
| `AUDITORIA_SEMANTICA_GRABADOR.md` | **nuevo**: este informe | entregable |
| `REVISION_DIAGNOSTICO_GRABADOR.md` | aviso de que §§0, 6 y 8 quedan retirados | evitar que se lea como vigente |

**No modificados:** `data/hands_db.jsonl`, `recorder/record_hand.py`,
`recorder/recorder_live.py`, `tools/diagnostico_grabador.py`,
`motor/test_diagnostico_grabador.py`, el motor y sus modelos.

**[D]** Las correcciones de pruebas que este informe identificaría **no se han
aplicado**: el encargo pide auditar, no reparar, y varias cambian aserciones.

### 9.3 Pruebas

**[M]** `tools/diagnostico_grabador.py --validar` → **OK**.

**[M]** `pytest motor/test_diagnostico_grabador.py recorder` → **43 passed**.

**[M]** Suite completa `pytest motor`:

```
867 passed, 1 failed, 1 skipped, 5 xfailed, 3 warnings
```

**[M]** El único fallo es
`motor/test_cm004.py::test_ninguna_mano_tiene_una_bb_b_que_no_pueda_ser_la_ciega`
por `H_1196`, **conservado a propósito** y sin tocar su expectativa.

**[M]** Omitidas y esperadas de forma idéntica al estado de partida.

### 9.4 Lo que las pruebas NO prueban

**[D]** **867 pruebas pasan y la base no está validada.** Las cifras que fijan
reproducen el comportamiento de un clasificador al que se le piden preguntas
que la magnitud no puede responder (§ 3). Una suite verde sobre un modelo
semántico equivocado no es evidencia: es coherencia interna.

---

## Conclusión

**[C]** Lo que queda en pie: los ids se resuelven con el botón; el SHA no ha
cambiado; el 26,7 % de las manos lo capturó código que no está en el
repositorio; `amount` tiene cuatro semánticas y la dominante es un delta de
stack; 286 de 288 calls con `falta == 1.0` del grupo mayoritario tienen una
explicación mecánica; `amount == stack` se cumple en el 6,8 % de las acciones de
all-in.

**[D]** Lo que se retira: «dos grabadores», «el patrón de 1.0 es del ROI», «38
compromisos que validan el mapeo», y el uso de 5433/445/96 como aportaciones
válidas.

**[D]** La conclusión que más cambia el trabajo: **no hace falta más análisis del
JSONL.** El esquema no contiene el campo que distinguiría un incremento de un
nivel, y el código que lo contiene es posterior a la base. Lo único que cierra
la cadena es **capturar manos nuevas con el código actual** y recuperar el
grabador de julio.

**Ese es el cuello de botella, y no es de pruebas: es de evidencia.**

---
---

# PARTE II — PLAN DE ACTUACIÓN VERIFICABLE

Esta parte **no repite** los hallazgos de la Parte I. Los convierte en
decisiones ejecutables. Todo lo que aquí se afirma está respaldado por la
búsqueda descrita en § P3, que es nueva.

---

## P3. Resultado de la búsqueda del grabador histórico

### P3.1 Qué se revisó

| fuente | resultado |
|---|---|
| historial de git anterior al snapshot | **no existe**: `b97349e` (2026-08-12) es el commit más antiguo de los 136 |
| ramas | solo `main` |
| etiquetas | ninguna |
| stashes | ninguno |
| reflog | empieza el 2026-10-17 (trabajo reciente), nada anterior |
| **objetos colgantes de git** | **1280 blobs. Contienen 5 versiones del grabador** |
| `.pyc` en el árbol de trabajo | `recorder/__pycache__/poker_recorder_gui.cpython-39.pyc`, fuente del **2026-08-11** |
| copias `.bak` / `.orig` / `.old` | solo `data/hands_db.jsonl.bak` (2026-10-16), que es **dato**, no código |
| `recorder/poker_recorder_gui.py` | existe; `CreationTime` **2026-07-18**. Es un **wrapper GUI que delega en `recorder_live`** (`rl_mod.OUTPUT_PATH`, `rl_mod.MANUAL_WINNER`) |

**[C]** La GUI demuestra que **todo el pipeline de captura de julio pasaba por
`recorder_live`**, no por `record_hand`. Es la primera evidencia independiente
del programa productor, y no viene de la base de datos.

### P3.2 Versiones recuperadas

**[C]** De los 1280 blobs colgantes, cinco contienen el grabador:

| blob | tipo | fecha del **fuente** | contenido |
|---|---|---|---|
| `c283c25ab` | bytecode `.pyc` (Py 3.9) | **2026-08-11 17:24:22** (40998 B) | `_process_folds_and_lag`, `_reconstruct_preflop`, `_add_action` |
| `434d5e5df` | bytecode `.pyc` (Py 3.9) | **2026-09-11 10:16:17** (45851 B) | `_detect_deltas`, `_detect_river_check`, `_add_implied_checks`, `out['allin']` |
| `63702ea89` | **fuente .py** (1070 líneas) | sin fecha en cabecera | idéntica en semántica a la actual; `_add_action` **sin** `amount_type` |
| `583617c6f` | bytecode, magic `a70d0d0a` | posterior | tiene `amount_type`; **no descompilable** con Py 3.9 |
| `9ab6af08b` | documento (264 líneas) | — | notas de revisión, no código |

La fecha del fuente sale de la **cabecera del `.pyc`** (bytes 8-11, `mtime` del
`.py`). Es el dato que permite anclar cada versión a un momento.

### P3.3 La semántica cambió dentro del periodo capturado

**[C]** Desensamblando `c283c25ab` y leyendo `b97349e` (el snapshot), la
expresión del importe es:

```python
# version del snapshot (2026-08-12) y c283c25ab (2026-08-11)
diff        = round(old_stake_val - new_stake_val, 2)   # delta de stack
prior_total = <suma de las acciones previas del jugador en la calle>
amt         = round(diff + prior_total, 2)              # delta + acumulado
atype       = 'r' if amt > max_bet else 'c'
```

**[C]** Y desde `0a9cfe5` (2026-09-20), y en el bytecode `434d5e5df`
(fuente del 2026-09-11):

```python
delta = round((prev_stake or 0) - cur_stake, 2)        # delta PURO
amt   = self._round_bet(delta, run_max)
```

**[C]** Hay además una **tercera expresión** en el snapshot, línea 448, en una
rama distinta:

```python
diff = round(old_stake or 0, 2)     # SIN restar new_stake
amt  = round(diff + prior_total, 2)
```

**[O]** Esa rama usa el stack enteroOld en vez del descenso. Si se ejecutó,
produce importes desproporcionados. **[P]** No se puede determinar si llegó a
ejecutarse: no hay marca y el estado que la activa no se conserva.

### P3.4 La conversión ocurre dentro de una ventana de manos

**[C]** Transición de `_process_folds_and_lag` (nivel) a `_detect_deltas`
(delta puro) entre **2026-08-12** y **2026-09-11**.

**[C]** No hay ninguna mano capturada entre 2026-08-11 17:24 y 2026-08-12 13:29,
así que la transición **no divide** ninguna ventana de captura. Sí cae dentro
de la ventana W3 (18 manos), donde hay que mirar mano por mano.

**[C]** `amount_type` entró en `8bd55be`, **2026-10-13 13:12:33**. La última mano
de la base es del **2026-09-18**. **Cero manos** se capturaron con código que
escribiera ese campo. Esto confirma por fecha lo que ya se sabía por conteo.

---

## P1. Matriz de procedencia y semántica

### P1.1 Criterios

Se usan **dos evidencias independientes**, ninguna derivada de la base:

1. **La cabecera del `.pyc`**: `mtime` del fuente al compilarlo.
2. **La fecha de la mano** (`hand['date']`), que es del reloj del grabador.

**No se usa la ausencia de `allin` ni la presencia de `winner` como
identificador del programa.** Son propiedades del dato, no evidencia de quién
lo escribió. Se reportan aparte, como descriptores.

### P1.2 Ventanas y conteos

| ventana | criterio | manos | con `allin` | sin `allin` |
|---|---|---:|---:|---:|
| **W1** | fecha < 2026-08-11 17:24 | **336** | 263 | 73 |
| **W3** | 2026-08-12 → 2026-09-11 | **18** | 18 | 0 |
| **W4** | ≥ 2026-09-11 | **904** | 904 | 0 |
| | **total** | **1258** | 1185 | 73 |

**[C]** Las 73 sin `allin` caen todas en W1. **[I]** Eso es coherente con que
`out['allin']` se introdujera entre el 11 y el 12 de agosto, pero **no lo
demuestra**: la ausencia del campo es consistente con esa hipótesis y también
con un fallo de escritura.

### P1.3 Clasificación por mano

| categoría | definición | manos |
|---|---|---:|
| **Procedencia confirmada** | existe el código exacto, con fecha, y la mano cae dentro de su ventana | **0** |
| **Procedencia temporal probable** | el código que la produjo se acota en el tiempo, pero no se recuperó esa versión | **336** |
| **Semántica de `amount` confirmada** | la expresión se lee en código recuperable y la mano cae en su ventana | **904** |
| **Semántica de `amount` inferida** | el código está en el repo pero la captura usó un árbol de trabajo sin commitear | **18** |
| **Semántica de `amount` indeterminada** | ninguna versión recuperada cubre la fecha | **0** |

**[C]** Sobre las 904 de W4, la expresión `delta = round((prev_stake or 0) -
cur_stake, 2)` está **desensamblada del bytecode** cuya cabecera fecha el
fuente el 2026-09-11, y las manos van del 11-09 al 18-09.

**[I]** Esa association es **probable, no confirmada**: el `.pyc` prueba que
existió una versión con esa expresión en esa fecha, no que fuera la que escribió
esas manos.

### P1.4 Clasificación por acción

| ruta de origen | acciones | magnitud | estado |
|---|---:|---|---|
| preflop reconstruido desde snapshot | 3710 | nivel absoluto de caja | semántica **confirmada** por código |
| delta de stack (rama normal) | 2264 | incremento | **confirmada en W4**, **inferida en W3** |
| rama `diff = round(old_stake or 0, 2)` | **desconocido** | stack entero + acumulado | **indeterminada**, sin marca que la identifique |
| fusión de `c`/`b` consecutivos | **desconocido** | suma de deltas = nivel | **indeterminada**: no queda rastro de qué se fusionó |
| checks `x` del grabador | 2856 − 23 | 0.0 por construcción | **inferidos, sin marca** |
| `x` inyectados por post-proceso | **23** | 0.0 | **confirmados** (`inferred: True`) |

**[C]** De 2856 acciones `x`, **solo 23 llevan marca**. Las otras 2833 son
indistinguibles de un check observado.

---

## P2. Qué se puede reconstruir de `amount`

| aspecto | nivel observado | delta puro | preflop de snapshot | fusionado | inferido |
|---|---|---|---|---|---|
| **Magnitud** | caja del jugador en la calle | chips que salieron del stack entre dos fotogramas | caja al abrir la mano | suma de varias acciones | 0.0 por construcción |
| **Unidad temporal** | acción (caja acumulada) | acción (incremento) | acción | **varias acciones** | ninguna |
| **Acumulación con anteriores** | **sí**, es un nivel | **no**, es un incremento | **sí** | **no**, ya es la suma | n/a |
| **Aportación incremental** | `amount − previa` | **`amount` directamente** | `amount` si no hay ciega previa | no recuperable | 0.0 |
| **Comparar con apuesta viva** | **válido** | **inválido** salvo primera call | **válido** | **válido** | n/a |
| **Evidencia de all-in** | ninguna por sí sola | `cur_stake is None` en el grabador | ninguna | ninguna | n/a |
| **Qué faltaría** | — | — | — | **el desglose de las acciones fusionadas** | **la marca de inferencia** |

**[D]** La fila de «apuesta viva» es la que invalida el diagnóstico: la regla
`max(viva, amount)` **[C]** es correcta para W1 y errónea para W4, y la base
mezcla ambas.

### P2.1 La prueba empírica

**[C]** El cambio de semántica **predice un patrón observable distinto**, y el
patrón aparece donde la predicción lo dice:

| ventana | semántica | calls | cortas | % | de las `falta == 1.0`, con previa ≈1.0 |
|---|---|---:|---:|---:|---:|
| **W1** (< 11-ago) | delta + acumulado = **nivel** | 671 | 107 | 15.9 % | **14.8 %** |
| **W4** (≥ 11-sep) | **delta puro** | 1887 | 391 | 20.7 % | **99.3 %** |
| total | | 2558 | 498 | 19.5 % | 337 |

**[C]** Los BB también se comportan distinto:

| ventana | calls BB | cortas BB | % |
|---|---:|---:|---:|
| W1 | 118 | 55 | 46.6 % |
| W4 | 328 | 196 | 59.8 % |

**[C]** En W4, 281 de 283 casos tienen aportación previa ≈1.0: mecánica
delta/nivel. En W1, solo 8 de 54: **otra causa, no identificada**.

**[D]** Consecuencia para el plan: **la métrica «calls por debajo de la viva» no
tiene un significado único en la base.** Hay que publicarla por ventana o
retirarla.

---

## P4. Clasificación de las métricas publicadas

| métrica | veredicto | motivo |
|---|---|---|
| **IDs → posición** | **válida** | `get_position` es determinista y no depende de `amount` |
| **Recuento de manos por fecha** | **válida** | `hand['date']` es dato directo |
| **Agrupación por ventana W1/W3/W4** | **válida con restricción** | depende de la fecha del `.pyc`, que es una **[I]**, no una **[C]** |
| **Semántica de `amount` en W4** | **válida con restricción** | bytecode recuperado; la asociación mano→versión es **[I]** |
| **Semántica de `amount` en W1** | **válida con restricción fuerte** | dos versiones independientes la confirman; la más antigua no está |
| **`calls` totales (2558)** | **válida** | conteo puro, no depende de la semántica |
| **calls cortas (498)** | **válida como conteo, inválida como anomalía** | mezcla dos poblaciones con semántica distinta |
| **falta de 1.0 del BB** | **inválida como diagnóstico** | 99.3 % en W4 es mecánica; en W1 es otro fenómeno sin explicar |
| **Aportaciones incrementales (`importe − previa`)** | **inválida en W3 y W4** | resta niveles de deltas |
| **Clasificación b/c/r** | **válida con restricción** | la letra la fija el grabador; su significado depende de la ventana |
| **All-ins** | **válida solo como campo declarado** | 201 manos; `amount == stack` **no** es evidencia |
| **Aportaciones totales por mano** | **inválida** | mezcla cajas, deltas yLevels; y hay acciones fusionadas sin desglose |
| **Reconstrucción del bote** | **pendiente** | `final_pot` es OCR (`max(max_pot, pot)`), no suma de aportaciones |
| **Acciones observadas / fused / inferidas** | **parcial** | 23 de 2856 `x` marcadas; la fusión no deja rastro |
| **5433 / 445 / 96** | **inválida** | reglas que comparan magnitudes incompatibles |

**[D]** Regla de publicación: **ninguna cifra de aportación debe salir sin la
ventana a la que pertenece.**

---

## P5. Diseño propuesto del esquema de captura futura

**[P]** Propuesta. **No implementada.**

### P5.1 El problema de fondo

Un `amount` es hoy un número sin cualidad. Para que una cantidad **reconstruida**
no se confunda con una **observada**, el esquema necesita separar tres ejes:
**origen**, **magnitud** y **temporalidad**.

### P5.2 Registro por acción

```json
{
  "pos": "BB",
  "action": "c",
  "amount": 3.0,

  "amount_type": "delta",
  "origin": "stack_delta",

  "seq": 3,
  "frame": 148,
  "street_started_frame": 142,

  "live_before": 3.0,
  "prev_same_player": { "seq": 1, "amount": 1.0, "amount_type": "delta" },

  "inferred": false,
  "inference_method": null,

  "merged_from": null,
  "observability": "observed"
}
```

### P5.3 Los cinco valores que el encargo pide distinguir

| valor | `amount_type` | `origin` | notas |
|---|---|---|---|
| nivel absoluto observado | `observed` | `bet_box` | la caja tal cual se leyó |
| incremento / delta | `delta` | `stack_delta` | el caso dominante actual |
| reconstruido de un snapshot | `observed` | `preflop_reconstruct` | **debe llevar `reconstructed: true`** |
| fusionado | `merged` | `street_merge` | + `merged_from: [seq...]` |
| inferido | `observed` | `implied_check` \| `state_label` \| `river_stable` | + `inference_method` |

### P5.4 Reglas que no se pueden relaxing

1. **[P]** `amount_type` **obligatorio**, con `ValueError` si falta, como ya
   hace `_add_action`.
2. **[P]** **Un valor reconstruido nunca puede llevar `amount_type:
   "observed"` sin `reconstructed: true`.** Es la confusión exacta que produjo
   este informe.
3. **[P]** **Toda acción fusionada conserva `merged_from`** con la lista de
   `seq` originales y su importe. Sin eso, la fusión es irreversible.
4. **[P]** **Ninguna acción inferida puede llevar `amount` numérico sin
   `inference_method`.** Un check vale 0 por construcción, no por lectura.
5. **[P]** **`frame` es obligatorio** en cada acción. Sin él no se puede
   distinguir un eco de una lectura obsoleta — que es lo que dejó a `H_0039`
   sin explicación.

### P5.5 Validación con manos controladas

**[P]** Antes de confiar en el esquema, capturar manos de situación **conocida**
por construcción y comprobar contra lo esperado:

| situación controlada | qué valida |
|---|---|
| SB fold, BB check | `x` del BB con `inference_method` correcto |
| BB sube, UTG iguala | `delta` del BB y de UTG por separado |
| BB all-in corto | `live_before` y `cur_stake is None` |
| check–check en river | que `confirm_all_check` llegue a `_add_implied_checks` |
| dos calls del mismo jugador separadas | que **no** se fusionen, o que la fusión deje rastro |

---

## P6. Plan priorizado para corregir las pruebas

### P6.1 Inventario con veredicto

| prueba | afirma | tipo | circular | qué debería haber comprobado |
|---|---|---|---|---|
| `test_la_base_son_dos_grabadores` | 1185 / 73 y `H_0001..H_0073` | estructura | **sí**: recalcula con `allin` | una fecha de versión, no un conteo |
| `test_el_campo_allin_no_lo_escribe_record_hand` | `allin` no identifica al grabador | caracterización | no | **[C] correcta; contradice a la anterior** |
| `test_la_apertura_no_tiene_la_misma_forma_en_los_dos` | distribuciones distintas | estructura | **sí**: recalcula | qué las diferencia, no que difieren |
| `test_las_498_no_las_503` | 498 | estructura | **sí** | por qué 498 es un hecho y no un artefacto |
| `test_la_clasificacion_sobre_la_base` | 5433/445/96 | estructura | **sí** | nada: la cifra no es interpretable |
| `test_el_desglose_por_accion_por_resultado_es_coherente` | matriz 2D | estructura | **sí** | que las columnas signifiquen algo |
| `test_las_repeticiones_no_son_consecutivas` | 26 / 0 consecutivas | estructura | **sí** | si la fusión explica las repeticiones |
| `test_los_ids_se_resuelven_con_el_boton` | 202 ids resueltos | **validez** | no | correcta: no depende de `amount` |
| `test_el_allin_no_esta_confirmado` | `amount == stack` no prueba all-in | **validez** | no | correcta |
| `test_h0546_el_allin_apunta_al_que_se_fue` | `allin` de H_0546 correcto | **validez parcial** | no | correcta para el `allin`; no para el `winner` |
| 4 tests `detect_actions` | letra de `record_hand` | caracterización | no | modelan un grabador que **no produjo ninguna mano** |
| 6 tests `[DEFECTO]` | comportamiento actual | caracterización | no | correctos como caracterización; **nunca como validación** |

### P6.2 La contradicción, resuelta

**[C]** Las dos pruebas se contradicen y **ambas pasan**:

- `test_la_base_son_dos_grabadores` deriva la procedencia de la presencia de `allin`.
- `test_el_campo_allin_no_lo_escribe_record_hand` demuestra que eso **no** identifica al programa.

**[D]** La segunda es la correcta. **La primera debe retirarse**, no reescribirse:
su premisa es falsa, y cualquier variante que conserve `allin` como
identificador seguiría siendo incorrecta. La replaces con una que use
**fechas contra la cabecera de los `.pyc`**, que es evidencia independiente.

### P6.3 Qué hacer con cada grupo

| acción | pruebas |
|---|---|
| **retirar** | `test_la_base_son_dos_grabadores`, `test_la_apertura_no_tiene_la_misma_forma_en_los_dos` |
| **reescribir** | `test_las_498_no_las_503` → por ventana; `test_las_repeticiones_no_son_consecutivas` → declarar que la fusión es indistinguible |
| **conservar** | `test_los_ids_se_resuelven_con_el_boton`, `test_el_allin_no_esta_confirmado`, `test_h0546_...` |
| **marcar como caracterización** | las 6 de `[DEFECTO]` y las 4 de `detect_actions`, con un prefijo `test_caracteriza_` |
| **sustituir** | los recuentos absolutos por **aserciones de coherencia por ventana**, nunca de valor |

**[D]** Regla que evita la repetición: **ninguna prueba debe calcular una cifra
con la misma regla que pretende validar.** Si el valor no tiene interpretación
independiente, la prueba es documentación, y debe llamarse así.

### P6.4 La prueba que habría detectado el error original

**[P]** Una prueba que, para cada acción, compruebe que **existe una versión de
código con fecha que la precede**, y que afirme la expresión del importe de esa
versión. Con eso, el cambio de `delta + prior_total` a `delta` puro se habría
detectado al escribirse la base, no dos fases después.

---

## P7. Vía A, vía B o ambas

### P7.1 Vía A — recuperación histórica

| | |
|---|---|
| **qué se ha recuperado** | 1 versión en fuente (`63702ea89`) y 2 en bytecode (`c283c25ab` 08-11, `434d5e5df` 09-11) |
| **qué cubre** | desde el **2026-08-11**. Las 922 manos de W3+W4 |
| **qué no cubre** | las **336** de W1 (2026-07-27 → 08-09) |
| **recapacidad** | confirmar la expresión del importe de 922 manos |
| **fiabilidad** | **alta** para el bytecode: es el código compilado. **Media** para la fuente recuperada: su fecha se desconoce |
| **esfuerzo** | bajo: ya está hecho; falta documentarlo |
| **limitación** | no hay fecha de fuente en `63702ea89`, y el bytecode no es ejecutable tal cual |

### P7.2 Vía B — nueva captura

| | |
|---|---|
| **qué exige** | el esquema de § P5, con `amount_type`, `origin`, `frame`, `merged_from` |
| **recapacidad** | **ninguna retrospectiva**. Solo hacia adelante |
| **fiabilidad** | **muy alta**: cada acción declara su origen |
| **esfuerzo** | medio: cambio de esquema y validación con manos controladas |
| **limitación** | no responde por las 1258 manos ya grabadas |

### P7.3 Comparación

| criterio | vía A | vía B |
|---|---|---|
| manos que recupera | **922** de 1258 (73 %) | 0 retrospectivas |
| manos que confirma hacia adelante | 0 | todas |
| fiabilidad de la evidencia | alta (bytecode) | muy alta (autodescriptiva) |
| resuelve el «BB 1.0» | **parcial**: separa W1 de W4, no explica W1 | n/a |
| effort | ya invertido | pendiente |

### P7.4 Recomendación

**[D] Ambas, y en este orden:**

1. **Primero, vía A ya está hecha.** Documentar las versiones recuperadas y
   publicar las métricas **por ventana**. Esto solo cuesta escribir, y convierte
   922 manos de «semántica indeterminada» en «semántica confirmada».
2. **Segundo, vía B**, pero **sin bloquear el análisis de W1**: el esquema nuevo
   no toca la base y puede empezar cuando se quiera.
3. **Las 336 manos de W1 se declaran condicionales.** **[D]** No son
   irrecuperables por definición: si aparece el `.pyc` o el fuente de julio, se
   resuelven. **[P]** Hoy no hay ninguna fuente en el repositorio, en los
   objetos colgantes, en el reflog, en las ramas, en las etiquetas ni en los
   archivos de copia.

**[D]** Lo que **no** se debe hacer: reconstruir las aportaciones de W1
asumiendo que su `amount` es un delta. **[C]** Las dos versiones
independientes que la cubren usan `delta + prior_total`, y los datos de W1 lo
confirman: solo el 14.8 % de sus faltas de 1.0 tienen lanowrap previa ≈1.0,
contra el 99.3 % de W4. Asumir el delta en W1 produciría exactamente el error
que este informe corrige.

---

## P8. Verificación de esta fase

**[M]** SHA-256 de `data/hands_db.jsonl` antes y después:
`35727961646dfaba2c67fd5ee0dbe9b0669d3156f9c6f3fa3585060a93f097e2` — **sin
cambios**. 1 782 206 bytes, 1258 líneas.

**[M]** No se modificó ningún grabador, ni `motor/`, ni la base.

**[M]** Archivos modificados: `AUDITORIA_SEMANTICA_GRABADOR.md` (este documento).
Los artefactos de investigación se escribieron en `%TEMP%\opencode\`, fuera del
repositorio.

**[M]** No se hizo commit.

**[D]** No se ejecutó código histórico sobre la base: los `.pyc` se
desensamblaron, no se importaron.

---

## Conclusión de la Parte II

**[C]** El grabador histórico **parcialmente sí se ha recuperado**: 1280 blobs
colgantes contenían cinco versiones, tres recuperables, **fechadas por la
cabecera del `.pyc`**. Eso cubre desde el 2026-08-11.

**[C]** Y el hallazgo que lo cambia todo: **la semántica de `amount` cambió
dentro del periodo capturado**, de `delta + acumulado` (nivel) a `delta` puro.
El corte cae entre el 11 y el 20 de septiembre, y **los datos lo confirman**:
el patrón de «falta 1.0 con aportación previa ≈1.0» aparece en el 99.3 % de W4
y en el 14.8 % de W1.

**[D]** Por tanto la base **no es homogénea en semántica**, y la afirmación
anterior de que «la rama dominante es el delta» era correcta pero
incompleta: es correcta para el 72 % y falsa para el 27 % que no tiene versión
recuperada.

**[D]** Lo que decide el plan es una frase: **922 manos se pueden confirmar ya,
336 quedan condicionales, y el resto depende de un archivo que no está en
ningún sitio del repositorio.** Ninguna cifra de aportación debería publicarse
sin la ventana a la que pertenece.

> ## ⚠️ Leer la PARTE III antes que esta conclusión
>
> La frase de arriba **está retirada**. La PARTE III corrige dos excesos de esta
> parte: (a) **no** hay 922 manos con procedencia confirmada — la procedencia
> confirmada es de **0 manos sobre 1258**; (b) el hueco de 31,7 días **no** es
> un hueco de captura, sino de lo que se conservó en este fichero.
>
> También corrige una cifra: el patrón de falta de 1,0 en W1 es del **6,1 %**,
> no del 14,8 % que aquí se cita (medición con definiciones distintas).

---
---

# PARTE III — CIERRE ANALÍTICO

## 0. Corrección aceptada

**[C]** En la Parte II escribí «904 manos con semántica de `amount`
confirmada». **Eso no se sostiene y se retira.**

La distinción correcta es la que ya usa el propio informe:

| | |
|---|---|
| **Semántica de una versión de código** | **confirmada** — se lee en el fuente o en el bytecode |
| **Que esa versión produjera una mano concreta** | **no se ha confirmado para ninguna mano** |

**[C]** La procedencia confirmada es de **0 manos sobre 1258**. Las 1258 son,
en el mejor caso, **temporal probable**. Que exista una versión compatible en la
ventana no demuestra qué código se ejecutó.

**[C]** La Parte II se sobreafirmó en un punto más: dijo que \hand_id\ y
`date` monótonos respaldaban «una sola secuencia de captura». No es así:
`_ensure_hand_id` deriva el contador del fichero
(`self._last_hand_id(self.output_path)`), así que los ids **se reconstruyen al
abrir el proceso**. La monotonía no prueba continuidad entre sesiones.

---

## 1. Comprobación 1 — Validación de los límites de las ventanas

**[C]** La partición es **exhaustiva, exclusiva y sin huérfanos**.

| comprobación | resultado |
|---|---|
| suman las ventanas | 336 + 18 + 904 = **1258** = total de la base |
| manos fuera de toda ventana | **0** |
| manos en dos ventanas | **0** (límites excluyentes por construcción) |
| fechas parseables | 1258 / 1258 |
| `hand_id` vs fecha, inversiones | **0 de 1257** |

**[C]** Ningún límite parte un grupo de manos:

| límite | origen | separación a ambos lados |
|---|---|---|
| T1 = 2026-08-11 17:24 | cabecera `.pyc` `c283c25ab` | 31,7 días |
| T2 = 2026-08-12 13:29 | commit `b97349e` | 31,7 días |
| T3 = 2026-09-11 10:16 | cabecera `.pyc` `434d5e5df` | 3,3 días |
| T4 = 2026-09-20 15:21 | commit `0a9cfe5` | no parte grupo |

**[C]** Esto es más fuerte de lo que parecía: como las transiciones caen en
huecos de **días**, la atribución no depende de desempates. Ninguna mano queda
«en el límite».

**[C]** Las ventanas no son segmentos de un flujo sino **sesiones**: 15 en total
(corte de 6 h de inactividad), repartidas **7 / 1 / 7**.

**[O]** W3 son **18 manos en una sola sesión de 17 minutos** el 2026-09-10. No
es una muestra, es un episodio.

### 1.1 Corrección: el hueco de 31,7 días no es un hueco de captura

**[C]** En el hueco 2026-08-09 19:32 → 2026-09-10 11:19 hay **419 manos** en
ficheros laterales (`recorder/hands_db_old.jsonl`, `recorder/hands_db.jsonl`)
que **no están en la base canónica**.

**[D]** Por tanto «la captura fue episódica» era una lectura equivocada de la
base canónica. Lo que es episódico es **qué se conservó**, no qué se grabó.

---

## 2. Comprobación 2 — Métricas recalculadas por ventana

**[C]** Reconciliación previa, con una única definición aplicada:

| | W1 | W3 | W4 | total |
|---|---:|---:|---:|---:|
| manos | 336 | 18 | 904 | 1258 |
| calls | 643 | 28 | 1887 | **2558** = publicado |
| calls cortas | 98 | 9 | 391 | **498** = publicado |
| `falta == 1.0` | 49 | 5 | 283 | **337** = publicado |

### 2.1 Con la definición adecuada a cada ventana

| ventana | fórmula de «alcanza la viva» | alcanzan | % | versión ingenua | % |
|---|---|---:|---:|---:|---:|
| **W1** (`amount` = nivel) | `amount >= viva`, siempre válida | 362 | **56,3 %** | 362 | 56,3 % |
| **W3** | **N/A** | — | — | — | — |
| **W4** (`amount` = delta) | válida **solo si el jugador no había aportado antes** | 1448 | **76,7 %** | 1496 | 79,3 % |

**[C]** En W1 la definición correcta y la ingenua **coinciden** (362 = 362): en
un nivel de calle son la misma regla. En W4 **difieren** (1448 vs 1496), y la
ingenua cuenta como «alcanza» 48 calls de jugadores que ya habían aportado, que
en delta **no** alcanzan la viva.

**[C]** Esa divergencia es la que predice el cambio de implementación. No es una
comprobación independiente, pero es coherente con él y no lo contradice.

### 2.2 Aportación incremental: dos fórmulas, dos resultados

| ventana | fórmula | acciones | fichas/mano | fichas/acción |
|---|---|---:|---:|---:|
| **W1** | `amount − acumulado previo` | 1354 | 20,3 | 5,04 |
| **W3** | **N/A** | — | — | — |
| **W4** | `amount` (ya es el delta) | 4533 | 22,5 | 4,48 |

**[C]** Magnitudes comparables (20,3 vs 22,5 fichas/mano). **[D]** Que ninguna
sea absurda es un control de coherencia, **no** una validación.

### 2.3 «Falta 1.0»: dos fenómenos

| ventana | `falta == 1.0` | con aportación previa ≈1,0 | % |
|---|---:|---:|---:|
| **W1** | 49 | 3 | **6,1 %** |
| **W3** | 5 | 5 | 100 % — pero son 18 manos, no significa nada |
| **W4** | 283 | 281 | **99,3 %** |

**[C]** W4: mecánica delta/nivel — el ciego del BB ya en la caja.
**[C]** W1: **6,1 %**. Otro fenómeno, sin explicar con los datos actuales.

**[D]** La cifra agregada **498 / 337 no debe usarse**: mezcla dos causas
distintas.

---

## 3. Comprobación 3 — Evidencia de despliegue

### 3.1 Lo que se buscó y no existe

| fuente | resultado |
|---|---|
| campo de versión / commit / build / run en el JSONL | **[C] NINGUNA.** Inventario completo: mano 11 claves, `players[]` 5, acción **4** (`action`, `amount`, `inferred`, `pos`) |
| fichero de log del grabador | **[C] ninguno** en el proyecto |
| la GUI registra versión | **[C] no**: `poker_recorder_gui.py` no menciona `version` ni `commit` |
| `hand_id` como evidencia de proceso | **[C] no lo es**: se deriva del fichero |

**[D]** **Respuesta a la pregunta: solo se pueden establecer intervalos
probables. Ninguna mano queda vinculada a una versión por evidencia directa.**

### 3.2 La única evidencia de despliegue que sí existe

**[C]** El campo `allin` **aparece en fronteras de sesión, nunca a mitad de
una**:

| sesión | fecha | `allin` |
|---|---|---|
| 1 | 2026-07-27 | 0 de 28 |
| 2 | 2026-07-28 | 0 de 45 |
| 3 | 2026-07-29 | 73 de 73 |
| 4–15 | 07-30 → 09-18 | todas |

**[C]** Ninguna sesión es mixta. **[I]** Eso acota un despliegue a la ventana
**2026-07-28 11:20 → 2026-07-29 11:47** (~24 h). **[D]** Es la mejor evidencia
de despliegue disponible, y aun así **no dice qué versión se desplegó**, solo que
hubo un redespliegue en ese punto.

**[C]** Segundo evento: el 2026-09-03 15:25 → 15:29 el grabador cambia el
fichero de salida (`hands_db_old.jsonl` → `recorder/hands_db.jsonl`).
**[C]** El `mtime` de `recorder/hands_db.jsonl` es **2026-09-11 10:16:17**,
idéntico al `mtime` del fuente de `434d5e5df`. **[I]** Ambos ficheros se
tocaron desde el mismo árbol de trabajo en el mismo minuto.

### 3.3 Lo que NO se ha resuelto

**[C]** Los límites temporales separan **ventanas de captura**, pero no dicen
qué versión había en el árbol de trabajo sin commitear en cada una.

**[D]** Como hubo días entre sesiones, **hubo tiempo de editar el código sin que
ninguna mano lo registrara**. La fecha acota; no determina.

---

## 4. Corrección material: la base canónica está incompleta

**[C]** Existen **22 manos que estuvieron en la base y ya no están**:

- **[C]** Están en `data/_backup_aplicar_correcciones/hands_db.jsonl` (1280
  líneas), versión anterior a las correcciones.
- **[C]** Fechan de **2026-08-11 10:48** a **2026-09-17 14:02**, cruzando las tres
  ventanas.
- **[C]** **`DOCS/SANEAMIENTO.md`, `DOCS/CANAL_MANUAL_CERRADO.md` y
  `DOCS/MIGRACION_CM001_CM003.md` mencionan 0 de las 22.**

**[D]** Una retirada sin registro no es lo mismo que una retirada con registro.
**[P]** Hay que averiguar si se documentaron en otro sitio antes de tratar 1258
como el conjunto cerrado.

**[C]** `recorder/hands_db.jsonl` (84 manos, 2026-09-03 → 09-10) es un **flujo de
captura distinto**, con ids `H_0001..H_0084` que **colisionan** con los de la
base canónica. Nunca se integró. **[D]** Los ids **no son únicos entre
ficheros**: usarlos como clave global sería un error.

**[C]** `recorder/hands_db_old.jsonl` comparte 648 de sus 667 ids con la
canónica; sus 19 propios están entre las 22 retiradas.

---

## 5. Estado final de la clasificación

| ventana | manos | procedencia | semántica de `amount` | métricas |
|---|---:|---|---|---|
| **W1** | 336 (27 %) | temporal probable | **probable** (dos versiones independientes coinciden) | **calculables** con fórmula de nivel |
| **W3** | 18 (1,4 %) | temporal probable | **indeterminada**: el cambio cae dentro | **N/A** |
| **W4** | 904 (72 %) | temporal probable | **probable** (bytecode fechado dentro) | **calculables** con fórmula de delta |

**[C]** Procedencia confirmada: **0**.
**[C]** Semántica confirmada **por versión**: sí (3 versiones).
**Semántica confirmada por mano**: **ninguna**.

### 5.1 Lo que queda publicable

**[D]** Sí, con la ventana a la vista:

- recuento de manos, sesiones y fechas
- reparto de acciones por tipo y posición **por ventana**
- `amount == stack` como **coincidencia descriptiva**, no como all-in
- en W4: las 281/283 faltas de 1,0 como **mecánica delta/nivel**
- en W1: las 46/49 restantes como **anomalía sin explicar**

**[D]** No:

- cualquier cifra de aportación **sin ventana**
- 5433 / 445 / 96 en cualquier forma
- 498 / 337 agregados
- las 18 manos de W3

---

## 6. Lo que haría falta para pasar de «probable» a «confirmado»

**[P]** En orden de rendimiento:

1. **Saber qué sesión ejecutó qué versión**. Con el `.py` recuperado basta si se
   sabe la sesión; sin eso, la asociación sigue siendo probable.
2. **Un registro de despliegue**: qué commit o `mtime` estaba en ejecución al
   arrancar cada sesión. Son 15 sesiones y bastaría una línea por sesión.
3. **El log de la GUI**, que ya escribe a pantalla (`_log`). Si se guardara a
   fichero, resolvería las 15 sesiones de golpe.
4. **[P]** Averiguar el destino de las 22 manos retiradas.

**[D]** Las cuatro son de proceso, no de análisis. **[D]** El límite real no es
que no sepamos interpretarlo: es que **el esquema nunca registró qué versión lo
escribió**.

---

## 7. Verificación de esta fase

**[M]** SHA-256 de `data/hands_db.jsonl` antes y después:
`35727961646dfaba2c67fd5ee0dbe9b0669d3156f9c6f3fa3585060a93f097e2` — **sin
cambios**. 1 782 206 bytes, 1258 líneas.

**[M]** No se modificó la base, ni los grabadores, ni `motor/`, ni las pruebas.

**[M]** `pytest motor/test_diagnostico_grabador.py recorder` → **43 passed**.
`pytest motor` → **867 passed, 1 failed, 1 skipped, 5 xfailed**. El único rojo
es `H_1196`, preexistente y sin tocar.

**[M]** Modificado: `AUDITORIA_SEMANTICA_GRABADOR.md` (este documento).
**Ningún commit.**

**[D]** No se implementó nada de § P6. La fase analítica queda cerrada con tres
puntos abiertos, todos de proceso: la asociación mano→versión, el destino de 22
manos, y las 18 manos de W3.

---
---

# PARTE IV — AUDITORÍA DE INTEGRIDAD HISTÓRICA

Restricciones de esta fase: no se modificó ninguna base, ni se eliminó,
restauró, fusionó ni reescribió ningún registro. No se tocó grabador, motor ni
pruebas. No hubo commit. Los `hand_id` **no** se usaron como identidad: todas las
comparaciones son por **huella de contenido**.

## 1. Inventario de fuentes, con hashes registrados antes de analizar

**[C]** Hashes tomados **antes** de cualquier comparación.

| ruta | bytes | líneas | SHA-256 | git |
|---|---:|---:|---|---|
| `data/hands_db.jsonl` | 1 782 206 | 1258 | `35727961646dfaba2c67fd5ee0dbe9b0669d3156f9c6f3fa3585060a93f097e2` | versionado |
| `data/_backup_aplicar_correcciones/hands_db.jsonl` | 1 799 795 | **1280** | `ec868e9305d1e03abbdcd688aa8f86d6f95ffac7cc57d04fbfe36c3a1f66778a` | no versionado |
| `data/_backup_aplicar_correcciones/hands_db.jsonl.antes_reinterpretacion` | 1 776 505 | 1258 | `202a1f548fc60bac3d0d4b7a225429083e22298d97a5f6f38cb28d24435b0634` | no versionado |
| `data/_backup_aplicar_correcciones/antes_ciegas_35727961646dfaba.jsonl` | 1 782 206 | 1258 | `35727961646dfaba…f097e2` | no versionado |
| `data/_backup_aplicar_correcciones/antes_sanear_31eba6e1c4824015.jsonl` | 1 782 162 | 1258 | `31eba6e1c4824015c1b149193ebfceacccb46b025673ea294a93bd486205bac5` | no versionado |
| `data/hands_db.jsonl.bak` | 1 782 025 | 1258 | `032bc79c0a18988c6bfeb8e1650cf633aafeadaae9439fb8fce80313f0429998` | no versionado |
| `recorder/hands_db_old.jsonl` | 945 694 | 668 | `e7fbae80fe60e019d8d3f4c52bf4138a8dd8e72bfad9b5bddeb8f96b432f32d9` | versionado |
| `recorder/hands_db.jsonl` | 122 723 | **84** | `9f1f61b53268df815a05e0284036bd9cf1fb7b90664af2f8401052104d68c07b` | versionado |

**[C]** `antes_ciegas_…jsonl` tiene **el mismo hash que la canónica**: es copia
redundante, no una versión distinta.

**[C]** `recorder/hands_db_old.jsonl` es el **único** fichero con líneas que no
son JSON válido: **1 de 668**. Las otras 667 se leen.

**[C]** Los cinco ficheros `test_*.jsonl` (1 línea cada uno) y
`shadow_hierarchy.jsonl` (229) son salidas de prueba y telemetría, **no** manos.
Se inventariaron y se descartan como fuentes de manos.

### 1.1 Búsqueda de fuentes adicionales

**[C]** Se recorrió todo el árbol del proyecto. **No se buscó fuera de él.**

| buscado | resultado |
|---|---|
| `**/*.jsonl*` en el proyecto | 14 ficheros, los 8 de la tabla + 6 de prueba |
| blobs colgantes de git (1280) | solo artefactos de `.py`, ningún `.jsonl` |
| ramas, etiquetas, stashes | ninguno adicional |
| reflog | empieza 2026-10-17, nada previo |

---

## 2. Huella de contenido usada para comparar

**[P]** Definida para esta fase. **No es identidad**: sirve para localizar
candidatas.

```
huella(mano) = json.dumps(
    {k: v for k, v in mano.items() if k ∉ {hand_id, date}},
    sort_keys=True, ensure_ascii=False)
```

**[C]** Se excluyen **`hand_id`** (contador reconstruido al arrancar, § P0 de la
Parte III) y **`date`** (reloj, no contenido). Se incluyen `players`,
`streets` (acciones y board), `btn_player`, `btn_idx`, `comunitarias`,
`final_pot`, `showdown`, `winner`, `allin`.

**[D]** **Límites declarados:** dos registros de la misma mano pueden diferir
legítimamente por una corrección aplicada, por un campo añadido después
(`inferred`, `amount_type`) o por capturarse en momentos distintos. Una
diferencia de huella **no** prueba que sean manos distintas; una coincidencia
**no** prueba que sean la misma.

---

## 3. Las 22 manos ausentes, una a una

**[C]** Procedencia del hallazgo: el commit **`75bbdb7`** (2026-10-14 17:11:49)
pasó el fichero de **1280 a 1258** líneas. **Exactamente 22 borradas, 0 nuevas,
52 modificadas in situ.**

**[C]** Para las 22 se comparó su huella contra **todas** las manos de la base
actual. **Ninguna tiene coincidencia de contenido**, ni bajo su propio id ni
bajo otro.

| id | fecha | acciones | board | huella | coincidencia en la base actual |
|---|---|---:|---:|---|---|
| H_0339 | 2026-08-11 10:48:29 | 6 | 3 | `4d1a…` | ninguna |
| H_0340 | 2026-09-03 15:12:29 | 6 | 0 | `9c02…` | ninguna |
| H_0341 | 2026-09-03 15:12:52 | 6 | 0 | `b733…` | ninguna |
| H_0342 | 2026-09-09 17:25:20 | 2 | 3 | `11e5…` | ninguna |
| H_0343 | 2026-09-09 17:25:24 | 12 | 5 | `77a9…` | ninguna |
| H_0344 | 2026-09-09 17:26:18 | 6 | 0 | `c418…` | ninguna |
| H_0345 | 2026-09-09 17:27:26 | 5 | 0 | `f0d2…` | ninguna |
| H_0346 | 2026-09-09 22:15:24 | 10 | 5 | `2b96…` | ninguna |
| H_0368 | 2026-09-13 19:48:30 | 13 | 5 | `83c1…` | ninguna |
| H_0379 | 2026-09-13 19:59:22 | 7 | 0 | `aa47…` | ninguna |
| H_0386 | 2026-09-13 20:34:50 | 6 | 3 | `5e20…` | ninguna |
| H_0410 | 2026-09-13 20:58:45 | 5 | 0 | `6b93…` | ninguna |
| H_0422 | 2026-09-13 21:07:02 | 6 | 0 | `cf71…` | ninguna |
| H_0446 | 2026-09-14 12:18:39 | 11 | 0 | `0d55…` | ninguna |
| H_0449 | 2026-09-14 16:09:01 | 4 | 0 | `3ea8…` | ninguna |
| H_0516 | 2026-09-14 17:01:52 | 4 | 0 | `78c2…` | ninguna |
| H_0583 | 2026-09-15 10:49:26 | 6 | 3 | `14bd…` | ninguna |
| H_0586 | 2026-09-15 10:51:31 | 5 | 3 | `9f60…` | ninguna |
| H_0603 | 2026-09-15 11:09:40 | **1** | 0 | `2b71…` | ninguna |
| H_0690 | 2026-09-15 14:46:56 | 6 | 3 | `7d04…` | ninguna |
| H_0705 | 2026-09-15 15:03:12 | 7 | 3 | `e819…` | ninguna |
| H_1015 | 2026-09-17 14:02:44 | 6 | 3 | `45ac…` | ninguna |

**[C]** También se compararon contra `recorder/hands_db_old.jsonl`: **0
coincidencias** de contenido y **0** registros idénticos completos.

### 3.1 Clasificación de las 22

| clasificación | nº | base de la clasificación |
|---|---:|---|
| **Mano distinta y aparentemente válida** | **22** | **[C]** estructura completa, 4–13 acciones, board coherente; **[C]** sin coincidencia con ninguna mano conservada ni con los ficheros laterales |
| Correspondencia confirmada | 0 | **[C]** no hay huella coincidente en ninguna fuente |
| Variante de una mano existente | 0 | **[C]** la búsqueda por huella y por registro completo no devuelve ninguna |
| Registro inválido o incompleto | 0 | **[C]** todas parsean, todas tienen `players` y `streets` |
| Indeterminada | 0 | — |

**[D]** «Aparentemente válida» es deliberado: significa que **el registro es
estructuralmente íntegro**, no que su contenido reflecting sea correcto. La
semántica de `amount` de estas manos sigue siendo la de su ventana, sin
confirmar (Parte III).

---

## 4. Evidencia sobre la retirada

### 4.1 Lo que sí está establecido

**[C]** La retirada **fue deliberada y está en el historial**. No es una pérdida
accidental:

| hecho | evidencia |
|---|---|
| el fichero pasó de 1280 a 1258 | **[C]** commit `75bbdb7` |
| fecha | **[C]** 2026-10-14 17:11:49 |
| exactamente 22 borradas, 0 añadidas | **[C]** diff de `data/hands_db.jsonl` en ese commit |
| el commit **también** modificó 52 manos in situ | **[C]** `streets`, `players`, `winner`, `final_pot` |
| el commit toca herramientas de saneamiento | **[C]** `tools/aplicar_reinterpretacion.py` (+121), `tools/auditar_rango.py` (+575) |

**[C]** El mensaje del commit es *«El "defecto de 652" eran 629 falsos
positivos, y un instrumento que se autocomprueba»*.

### 4.2 Lo que NO está establecido

**[C]** **El criterio que seleccionó esas 22 no queda demostrado.** La razón que
el mensaje declara **se refuta con los datos**:

| comprobación sobre el estado anterior al commit | resultado |
|---|---|
| de las 22, cumplen «el BB no actúa tras la subida» | **7 de 22 (32 %)** |
| de las 1258 que **permanecen**, cumplen lo mismo | **185** |
| de las 22, tienen ≤ 6 acciones | 16 |
| de las 1258 restantes, tienen ≤ 6 acciones | **246** |

**[D]** Si 185 manos que se quedan cumplen la regla que el mensaje da como
motivo, **esa regla no explica la retirada**. Y la escasez de acciones tampoco:
246 manos conservadas son igual de escasas.

**[D]** Se comprobó además una hipótesis alternativa —que fueran duplicados de
`hands_db_old.jsonl`— y **se descarta**: 0 coincidencias.

**[C]** Se revisó `motor/learn.py` buscando un mecanismo de exclusión. Existe
`EXCLUSIONES_VENTANA_FABLE` con **23 ids** (H_0031, H_0037, **H_0039**, …), pero
**no coincide con las 22** (ojo: `H_0039` ≠ `H_0339`) y **ese mecanismo no borra
nada**: deja las manos en el fichero y las saca solo de la «ventana fiable» de
análisis. Es otro mecanismo.

**[D]** Por tanto: **la operación que retiró las 22 es identificable (commit
`75bbdb7`), pero su criterio de selección no es reconstruible con la evidencia
disponible.** No se atribuye.

---

## 5. Colisiones del flujo secundario (`recorder/hands_db.jsonl`, 84 manos)

**[C]** Comparación por contenido, no por id:

| comprobación | resultado |
|---|---:|
| manos del flujo secundario | 84 |
| **cuyo `hand_id` choca con alguna de la canónica** | **84 de 84** |
| con **contenido idéntico** a alguna mano canónica | **0** |
| con contenido distinto | **84** |
| cuya `date` aparece en la base canónica | **0** |
| con contenido idéntico a alguna de las 22 ausentes | **0** |

**[C]** Las 84 son **manos diferentes con ids coincidentes**, en un periodo
(2026-09-03 → 09-10) en el que la base canónica **no tiene ninguna mano**.

**[D]** Esto confirma de forma directa lo que lo que la Parte III ya decía: **`hand_id`
no es identidad global**. Es un contador por fichero y por sesión, y hoy dos
ficheros distintos lo usan como si fuera la misma clave.

**[C]** La fuente de la colisión es conocida: `_ensure_hand_id` deriva el
contador del fichero de salida, y `OUTPUT_PATH` cambió el 2026-09-03 15:25 →
15:29 (de `hands_db_old.jsonl` a `recorder/hands_db.jsonl`).

**[D]** El flujo de 84 **no se fusiona ni se deduplica** en esta fase, y no hay
evidencia que lo vincule con la base canónica: 0 coincidencias de contenido y 0
de fecha.

---

## 6. Política propuesta de identidad y procedencia

**[P]** Propuesta. **No implementada.**

### 6.1 El problema que hay que evitar

Un id que se regenera al arrancar y que colisiona entre ficheros no puede ser
clave. **[C]** Las 84 colisiones lo demuestran con datos, no con una hipótesis.

### 6.2 Separar cinco identificadores

```json
{
  "hand_uid":      "sha256:session_id|local_seq",
  "session_id":    "2026-09-13T19:46:52/recorder/hands_db.jsonl",
  "local_seq":     41,
  "source_file":   "recorder/hands_db.jsonl",
  "source_sha256": "9f1f61b5…",
  "line_no":       42,
  "recorder_version":   {"git": "6b7f199", "source_mtime": "2026-09-11T10:16:17"},
  "schema_version": 3
}
```

**[P]** `hand_uid` se deriva de `session_id + local_seq`, no de un contador
global. Dos ficheros distintos **no pueden** producir el mismo `hand_uid`.

### 6.3 Trazabilidad por acción

```json
{
  "pos": "BB", "action": "c", "amount": 3.0,
  "amount_type": "delta",
  "origin": "stack_delta",
  "inferred": false,
  "inference_method": null,
  "merged_from": null,
  "seq": 3, "frame": 148
}
```

**[P]** Reglas: un valor **reconstruido** nunca lleva `amount_type: "observed"`
sin `reconstructed: true`; una acción **fusionada** conserva `merged_from`; una
acción **inferida** lleva `inference_method`; `frame` es obligatorio.

### 6.4 Manos corregidas y capturas repetidas

**[P]** **No se reescribe la mano corregida.** Se guarda la nueva y se enlaza:

```json
{
  "hand_uid": "…", "revision": 2,
  "supersedes": "sha256:…",
  "correction_reason": "CM-004",
  "corrected_at": "2026-10-14T17:11:49"
}
```

**[D]** Así las 52 modificadas in situ por `75bbdb7` habrían dejado rastro, y las
22 borradas habrían seguido existiendo con `retired_at` y `retired_reason`. **[D]
Nada de eso existe hoy: por eso esta fase no puede reconstruir el criterio.**

**[P]** Una captura repetida de la misma mano se guarda como `hand_uid`
distinto con `capture_group`, y **nunca** se deduplica automáticamente: la
decisión es del mantenedor.

---

## 7. Recomendación individual para cada una de las 22

**[D]** Las 22 comparten la misma situación probada, así que la recomendación es
uniforme **pero se aplica una por una**.

| opción | consequence |
|---|---|
| **mantener fuera** | la base queda en 1258; se pierde 22 manos capturadas, 3 de ellas del periodo sin código recuperado |
| **recuperar** | 1258 → 1280; cambia **todas** las cifras por ventana y el denominador de 1258 que usa toda la documentación |
| **tratar como variante** | **[D] no procede**: no hay mano existente de la que sean variante |
| **pendiente** | se mantiene el estado actual y no se altera nada |

**Recomendación: mantener fuera, con la decisión explícitamente pendiente.**

**[D]** Motivos:

1. **[C]** Ninguna es duplicado ni variante: no hay a qué fusionarlas.
2. **[C]** El criterio que las sacó no está establecido. Recuperarlas sin
   entenderlo **reintroduce un sesgo no medido**.
3. **[D]** Recuperarlas cambia los denominadores de todo lo publicado en las
   Partes I–IV, que ya están segmentados por ventana.
4. **[P]** Lo que sí procede ahora es **registrarlas** en el inventario de
   fuentes —ya lo están, § 1— y mantener el conjunto de 1280 disponible para
   análisis posteriores sin tocar la canónica.

**[P]** Si el mantenedor decide recuperarlas, el orden correcto es:
documentar primero el criterio de `75bbdb7`, luego decidir, y solo entonces
tocar el fichero. Nunca al revés.

**Sobre el flujo secundario:** **[D] conservarlo como fuente independiente**. No
hay evidencia que lo vincule con la canónica (0 de contenido, 0 de fecha), y
**no fusionarlo** hasta que exista esa evidencia.

---

## 8. Cuestiones que siguen sin resolverse

| # | cuestión | estado |
|---|---|---|
| 1 | **¿Qué criterio seleccionó las 22 en `75bbdb7`?** | **[D]** el mensaje se refuta; no hay código que lo implemente |
| 2 | ¿Por qué el mismo commit modificó 52 manos sin dejar registro? | **[D]** solo se sabe qué campos cambiaron |
| 3 | ¿Qué versión del grabador escribió cada una de las 22? | **[D]** sin marca de versión; 3 caen en el periodo sin código recuperado |
| 4 | ¿Son las 84 del flujo secundario útiles para algo? | **[P]** 0 vinculaciones con la canónica |
| 5 | ¿Hay una línea corrupta recuperable en `hands_db_old.jsonl`? | **[P]** 1 de 668; no se ha intentado repararla |
| 6 | ¿Cuál era la semántica de `amount` en `H_0339` (2026-08-11)? | **[D]** anterior a todo código recuperado |

**[D]** **La base no se declara completa ni corrupta.** Hay 22 registros
retirados sin criterio recuperable y 84 en un flujo no vinculado: son
discrepancias **descritas y acotadas**, no resueltas.

---

## 9. Verificación de esta fase

**[M]** SHA-256 de las fuentes tras el análisis — **todas sin cambio**:

| fuente | SHA-256 | ¿sin cambio? |
|---|---|---|
| `data/hands_db.jsonl` | `35727961646dfaba…f097e2` | **sí** — coincide con el esperado |
| backup 1280 | `ec868e9305d1e03a…` | sí |
| `recorder/hands_db_old.jsonl` | `e7fbae80fe60e019…` | sí |
| `recorder/hands_db.jsonl` | `9f1f61b53268df81…` | sí |

**[M]** Base canónica: **1 782 206 bytes · 1258 líneas · hash esperado**.

**[M]** No se modificaron datos, pruebas, grabadores ni motor. Modificado
únicamente: **`AUDITORIA_SEMANTICA_GRABADOR.md`**. **Ningún commit.**

**[M]** Pruebas: `motor/test_diagnostico_grabador.py recorder` → **43 passed**.
`pytest motor` → **867 passed, 1 failed, 1 skipped, 5 xfailed**; el único rojo
es `H_1196`, preexistente.

### 9.1 Limitaciones de esta fase

**[D]** Comparación por huella: una diferencia puede deberse a una corrección
legítima. No se ha reconstruido la secuencia de correcciones de cada
mano.

**[D]** `recorder/hands_db_old.jsonl` tiene 1 línea ilegible: **su análisis es de
667 de 668**, y no se ha intentado recuperarla.

**[D]** El criterio de `75bbdb7` sigue sin establecerse. Es la limitación
principal y **no se ha rellenado con una hipótesis**.

---
---

# PARTE V — CONTROL DE MULTIPLICIDAD

La Parte IV afirmó «22 manos ausentes» contando **registros**. Eso no es lo
mismo que 22 manos. Esta parte separa las cuatro magnitudes y corrige el marco.

## 1. Las cuatro cuentas, que no coinciden

**[C]** Se cuentan por separado, para cada fuente:

| fuente | líneas | registros válidos | contenidos distintos | duplicados internos |
|---|---:|---:|---:|---:|
| `data/hands_db.jsonl` | 1258 | **1258** | **1258** | **0** |
| backup 1280 | 1280 | 1280 | **1279** | **1** |
| `hands_db.jsonl.bak` | 1258 | 1258 | 1258 | 0 |
| `.antes_reinterpretacion` | 1258 | 1258 | 1258 | 0 |
| `antes_ciegas_…` | 1258 | 1258 | 1258 | 0 |
| `antes_sanear_…` | 1258 | 1258 | 1258 | 0 |
| `recorder/hands_db_old.jsonl` | 668 | **667** | 667 | 0 |
| `recorder/hands_db.jsonl` | 84 | 84 | 84 | 0 |

**[C]** Líneas ≠ registros válidos solo en `hands_db_old.jsonl` (**1 línea
corrupta de 668**).

**[C]** La base canónica **no tiene ni un solo duplicado interno**: 1258
registros = 1258 contenidos distintos = 1258 ids distintos.

**[C]** El backup de 1280 **sí tiene uno**: `H_0340` y `H_0341` tienen
**contenido idéntico**.

### 1.1 Las cifras reales de las 22

**[C]** Contra el predecesor inmediato en git (`02fc641`, 1280 registros):

| magnitud | valor |
|---|---:|
| **registros** ausentes en la canónica | **22** |
| **ids distintos** | **22** |
| **contenidos distintos** | **21** |
| contenidos de esos 22 que aparecen en la canónica | **0** |
| **manos cuya identidad puede establecerse** | **≤ 21**, y de esas 21 **ninguna** con certeza de ser mano distinta de la otra |

**[D]** La cifra correcta no es «22 manos ausentes» sino: **22 registros, 21
contenidos, y un número de manos reales que no puede determinarse.** El par
`H_0340`/`H_0341` es la razón.

---

## 2. El multiplicado del backup no era el predecesor

**[C]** Comparación multiconjunto, `backup1280` frente a canónica:

| | valor |
|---|---:|
| contenidos en **ambos** | **854** |
| contenidos **solo en el backup** | **425** |
| contenidos **solo en la canónica** | **404** |
| contenidos comunes con **multiplicidad distinta** | **0** |

**[C]** El fichero del backup es del **2026-10-07**. El commit que retiró las 22
es del **2026-10-14**. Entre ambas fechas se editaron contenidos.

**[D]** Por eso «no está en la canónica» **mezcla dos cosas distintas**: manos
que se perdieron y manos que después se corrigieron. La comparación ingenua
atribuye a la retirada casi cinco veces más manos de las que realmente se
retiraron (425 frente a 22).

**[C]** El predecessor real (`02fc641`, 1280 registros, **1279** contenidos) tiene
**1228 contenidos comunes** con el fichero del backup, y **51 únicos de cada
lado**. Tampoco es idéntico, pero es el que sí contiene las 22.

### 2.1 Cuadro completo contra la canónica

**[C]** `solo src` = contenidos de esa fuente ausentes de la canónica.
`solo can.` = contenidos canónicos ausentes de esa fuente, es decir
**contenido editado**, no mano perdida.

| fuente | regs | distintos | x-dup | en ambos | solo src | solo can. | **mult. dif.** |
|---|---:|---:|---:|---:|---:|---:|---:|
| backup 1280 | 1280 | 1279 | 1 | 854 | 425 | 404 | **0** |
| `hands_db.jsonl.bak` | 1258 | 1258 | 0 | 1255 | 3 | 3 | **0** |
| `.antes_reinterpretacion` | 1258 | 1258 | 0 | 943 | 315 | 315 | **0** |
| `antes_ciegas_…` | 1258 | 1258 | 0 | **1258** | **0** | **0** | **0** |
| `antes_sanear_…` | 1258 | 1258 | 0 | 1256 | 2 | 2 | **0** |
| `hands_db_old` (667) | 667 | 667 | 0 | **268** | 399 | 990 | **0** |
| flujo 84 | 84 | 84 | 0 | **0** | 84 | 1258 | **0** |

**[C] `mult. dif. = 0` en las siete fuentes.** Ningún contenido común aparece con
multiplicidad distinta en los dos lados. **No hay registros ocultos ni
candidatas consumidas de más.**

**[C]** `antes_ciegas_…` coincide **al 100 %** con la canónica: confirma que es
copia redundante, no una versión anterior.

**[C]** El flujo de 84 es **totalmente disjunto**: 0 contenidos en común.

**[C] Corrección a la Parte IV:** `hands_db_old.jsonl` **sí** comparte **268
contenidos** con la canónica. En la Parte IV se habló de ese fichero solo
como portador de las 19 manos propias, y esa lectura era incompleta.

---

## 3. Las cinco categorías que pediste separadas

| categoría | **registros** | **contenidos** | **manos identificables** |
|---|---:|---:|---:|
| **Registros adicionales en el backup** (contra `02fc641`) | 22 | 21 | ≤ 21 |
| **Contenidos distintos no encontrados en la canónica** | 425 | 425 | no determinable: mezcla ausentes y editadas |
| **Variantes posibles de manos canónicas** | **0** | 0 | 0 |
| **Duplicados internos** | 1 (en el backup) | 1 | — |
| **Identidad no determinable** | 2 (`H_0340`, `H_0341`) | 1 | **no determinable** |

**[C]** «Variantes posibles»: se buscaron por huella exacta (**0**), por fecha
exacta (**0**), y por coincidencia de board + jugadores + botón (**7**, con
fechas muy distintas, p. ej. `H_0446` 14-sep frente a `H_0079` 29-jul). **Ninguna
cumple el criterio de proximity.** Se registra como **0**, no como «7
probables».

**[C]** De los 22, **15 no tienen ninguna candidata cercana**; los otros 7 solo
comparten board, jugadores y botón, a **días o semanas** de distancia.

---

## 4. Ambigüedades que NO se resuelven

**[D]** No se deduplicó nada, no se fusionó nada, no se descartó nada.

| # | ambigüedad | tratamiento |
|---|---|---|
| 1 | **`H_0340` / `H_0341`**: contenido idéntico, **23 s** de diferencia | **[C]** indistinguibles por contenido. **[D]** son 2 registros y 1 contenido. **No se fusionan** y **no se declara** que sean la misma mano |
| 2 | **425 contenidos del backup** ausentes de la canónica | **[D]** mezcla manos retiradas y manos editadas después. La cifra «22» solo vale contra `02fc641` |
| 3 | **7 de los 22** con board/jugadores/botón coincidentes | **[D]** proximity débil, fechas a días o semanas. Se registran como candidatas, **no** como variantes |
| 4 | flujo 84 y `hands_db_old` | **[D]** no se puede establecer vínculo. El de 84 es **disjunto**; el otro comparte 268 contenidos pero **el origen de esa coincidencia no está explicado** |

**[D]** Sobre la ambigüedad 1: **[C]** una huella idéntica **no** demuestra que
sea el mismo evento real. Dos manos distintas pueden tener el mismo desarrollo
y los mismos importes; un mismo evento puede escribirse dos veces. **El dato no
decide entre las dos hipótesis y no se elige una.**

---

## 5. Corrección formal a la Parte IV

**[C]** La Parte IV afirmóó que las 22 eran «22 registros = 22 contenidos
distintos». **[C] Falso: son 22 registros y 21 contenidos**, porque `H_0340` y
`H_0341` colapsan. La clasificación «mano distinta y aparentemente válida» se
mantiene **para los 21 contenidos**, y para el par colapsado pasa a
**«identidad no determinable»**.

**[C]** La conclusión de fondo de la Parte IV **no cambia**: el commit
`75bbdb7` sigue siendo el que retiré 22 registros, el criterio sigue sin
establecerse, y ninguna de las 22 tiene contenido presente en la canónica.

---

## 6. Verificación

**[M]** SHA-256 de todas las fuentes **sin cambio**:

| fuente | prefijo SHA-256 |
|---|---|
| `data/hands_db.jsonl` | `35727961646dfaba` ✓ esperado |
| backup 1280 | `ec868e9305d1e03a` |
| `hands_db.jsonl.bak` | `032bc79c0a18988c` |
| `.antes_reinterpretacion` | `202a1f548fc60bac` |
| `antes_ciegas_…` | `35727961646dfaba` |
| `antes_sanear_…` | `31eba6e1c4824015` |
| `hands_db_old.jsonl` | `e7fbae80fe60e019` |
| flujo 84 | `9f1f61b53268df81` |

**[M]** Canónica: 1 782 206 bytes · 1258 líneas · hash esperado. **[M]** No se
modificó ninguna base, ni grabador, ni motor, ni pruebas. Modificado
únicamente `AUDITORIA_SEMANTICA_GRABADOR.md`. **Ningún commit.**

**[D]** Nota de proceso: queda anotada la convención de prefijar **«A1»** los
commits que se hagan a partir de ahora.

### 6.1 Limitaciones

**[D]** La huella no incluye `hand_id` ni `date`. Dos registros con distinta fecha
pero idéntico contenido colapsan: es lo que produce el caso `H_0340`/`H_0341`.

**[D]** Con fecha incluida serían 22 contenidos distintos y **0** duplicados. Que
haya duplicados o no depende de si `date` se considera parte de la identidad, y
**eso no está decidido**.

**[D]** `hands_db_old.jsonl` sigue analizándose sobre 667 de 668 registros; la
línea corrupta no se ha intentado recuperar.

**[D]** La base **no se declara completa ni corrupta**. Hay 1 ambigüedad de
identidad sin resolver, 425 contenidos de origen mixto sin desglosar y 6
preguntas abiertas desde la Parte IV.

---
---

# PARTE VI — AUDITORÍA DEL COMMIT QUE RETIRÓ 22 REGISTROS

Restricciones respetadas: no se modificó ninguna base, ni se restauró o eliminó
ningún registro, ni se tocó grabador, motor ni pruebas. **Ningún commit.**
El criterio de identidad no cambió: `hand_id` y `date` siguen excluidos de la
huella, y **`H_0340`/`H_0341` se mantienen como dos registros independientes con
identidad no determinable**.

## 1. Resumen del diff de `75bbdb7`

**[C]** Commit `75bbdb7e79c34fc85053784d5c303630b1655dbd`, autor `Jorgito
<jorgito@local>`, **2026-10-14 17:11:49 -0500**, asunto *«El "defecto de 652"
eran 629 falsos positivos, y un instrumento que se autocomprueba»*.

**[C]** 11 ficheros, 1678 inserciones y 88 borrados:

| fichero | cambio |naturaleza |
|---|---:|---|
| `data/hands_db.jsonl` | **52 añadidas / 74 borradas** | datos |
| `tools/auditar_rango.py` | +575 | **nuevo**, auditoría |
| `motor/test_aplicar_reinterpretacion.py` | +209 | **nuevo**, prueba |
| `DOCS/HALLZGOS_H0001_H1014.md` | +268 | **nuevo** |
| `DOCS/DEFECTO_652.md` | +136 | **nuevo** |
| `tools/aplicar_reinterpretacion.py` | +121 | modificado |
| `motor/test_rango_fiable.py` | +84 | **nuevo**, prueba |
| `DOCS/DEFECTO_214.md` | +87 | **nuevo** |
| `DOCS/DEFECTO_45.md` | +70 | **nuevo** |
| `DOCS/DEFECTO_8.md` | +56 | **nuevo** |
| `motor/test_cm004.py` | +34 | modificado |

**[C]** La aritmética del fichero de manos cuadra exactamente:
74 borradas − 52 añadidas = **22 netas**. Y 22 eliminaciones + 52 modificaciones
= 74 borradas. **[O]** **22 registros eliminados + 52 modificados in situ.**

### 1.1 ¿Eliminación directa o consecuencia de una transformación?

**[C] Consecuencia de una operación manual, no de un script.**

`tools/aplicar_reinterpretacion.py` **reescribe** el fichero (línea 313 del
fichero en ese commit), pero su función `aplicar_a_mano` (líneas 99-130) hace
`salida.append(...)` en **todos** los caminos: no existe ninguna rama que
`continue` sobre una mano completa. Solo modifica: CM-004 cambia `b`→`r` y
CM-002 cambia `cards: "-"`→`""`.

**[C]** Y las 52 modificaciones **sí corresponden a ese alcance**: 39 tienen la
firma exacta de CM-004 (una entrada `BB b` que pasa a `BB r`), 0 tienen la de
CM-002, 13 tienen otro cambio. **[C] El script se ejecutó.**

**[C]** `tools/auditar_rango.py` solo escribe un informe JSON
(`args.json_out`, líneas 562-563). No toca la base.

**[C]** Ningún fichero del commit —`.py`, `.md` o `.json`— menciona **ninguno**
de los 22 ids. La búsqueda sobre el árbol de `75bbdb7` devuelve vacío.

**[D]** **Las modificaciones fueron script; las 22 eliminaciones, no.** Nada en
el commit las produce, y nada en el commit las nombra.

---

## 2. Criterio de retirada:Declaración explícita de lo que hay

**[C] Se encontró un criterio escrito, y está incompleto y sin respaldo
verificable.**

### 2.1 Lo que dice la documentación

**[C]** `DOCS/PROYECTO.md`, líneas 733-735 (estado actual del fichero):

> - Nota operativa de `pegar_9.txt`: eliminar 20 manos concretas
>   (`H_0339`–`H_0346`, `H_0368`, `H_0379`, `H_0386`, `H_0410`, `H_0422`,
>   `H_0446`, `H_0449`, `H_0516`, `H_0583`, `H_0586`, `H_0603`, `H_0690`,
>   `H_0705`). ⚠️ `H_0340` está en ese rango y es el ejemplo de la inferencia
>   errónea de subida.

**[C]** Esa nota **enumera 21 ids** (8 del rango `H_0339`–`H_0346` más 13) y dice
**«20 manos»**. La nota es **internamente inconsistente en su propio recuento**.

**[C]** `H_1015`, que sí fue retirado, **no figura en la lista**.

### 2.2 La fuente que la nota cita

**[C]** `pegar_9.txt` **existe en el árbol de trabajo** y tiene **23 bytes**:

```
eliminar H_1123, H_1188
```

**[C]** Su `mtime` es **2026-10-16 11:38**, **dos días después** del commit que
retiró las 22. **[C]** `H_1123` y `H_1188` **siguen en la base canónica** y no
son de las 22.

**[D]** El fichero fue rotado o sobrescrito: su contenido actual **no es** la
lista documentada. **El contenido que tenía el 2026-10-14 no es recuperable.**

**[C]** `pegar.txt` (596 líneas) y `pendientes_pegar.txt` (207 líneas) existen y
**no contienen ni un solo id con el formato `H_####`**.

### 2.3 Corrección de las Partes IV y V

**[C]** Esas partes afirman que las 22 **no están documentadas en ninguna parte
del proyecto**. **[C] Es falso.** Se buscaron solo tres ficheros
(`SANEAMIENTO.md`, `CANAL_MANUAL_CERRADO.md`, `MIGRACION_CM001_CM003.md`) y se
concluyó de ahí. Una búsqueda en todo el árbol encuentra **20 de 22** en
`DOCS/PROYECTO.md` y **21 de 22** en `data/observations.json`.

**[C]** La nota que las nombra se añadió **después** del commit: los 5 DOCS de
`75bbdb7` no la contienen. **[D]** En el momento de la retirada **no existía
documentación del criterio**.

### 2.4 Los tres criterios candidatos, y por qué ninguno discrimina

**[C]** Se probaron tres hipótesis contra el estado anterior al commit:

| criterio | de las 22 | de las 1258 que se quedan |
|---|---:|---:|
| «el BB no actúa tras la subida» (mensaje del commit) | **7** | **185** |
| «la ciega del BB contada como open» (nota de `PROYECTO.md`) | **21** | **919 (73,1 %)** |
| BB con entrada y sin respuesta posterior | 16 | 454 |

**[C]** Ninguno separa los grupos. **[D]** Ninguno puede ser el criterio, porque
el criterio tendría que ser más frecuente en las retiradas que en las que
quedan, y los tres son más frecuentes en las que quedan.

### 2.5 Conclusión del criterio

**[C]** **Se encontró el origen documental de la lista** (`DOCS/PROYECTO.md`)
**y no se encontró el razonamiento que la respalda.** La lista dice *qué* mano
retirar; no dice *por qué* esa mano y no otra. La notaOperations con
`H_0340` solo lo identifica como ejemplo de un error de análisis —que es un
motivo para **excluirlo del análisis**, no para borrarlo de la fuente.

**[D]** Un registro no debe eliminarse porque moleste a una métrica. Esa es
justamente la razón que la nota sugiere para `H_0340`.

---

## 3. Tabla individual de los 22 registros

**[C]** Estado en `02fc641`. «válido» = tiene `players` y `streets`. «en doc» =
aparece en la lista de `PROYECTO.md`.

| id | fecha | BB preflop | acciones | válido | huella (8) | en doc | clasificación |
|---|---|---|---:|---|---|---|---|
| H_0339 | 2026-08-11 | `x` | 6 | sí | `b919ddf9` | sí | aparentemente justificada, sin prueba |
| H_0340 | 2026-09-03 | `b` | 6 | sí | `68ec36ea` | sí | aparentemente justificada, sin prueba |
| H_0341 | 2026-09-03 | `b` | 6 | sí | `68ec36ea` | sí | aparentemente justificada, sin prueba |
| H_0342 | 2026-09-09 | `bx` | 2 | sí | `6db928ae` | sí | aparentemente justificada, sin prueba |
| H_0343 | 2026-09-09 | `bx` | 12 | sí | `9cf58a11` | sí | aparentemente justificada, sin prueba |
| H_0344 | 2026-09-09 | `b` | 6 | sí | `7f6420fe` | sí | aparentemente justificada, sin prueba |
| H_0345 | 2026-09-09 | `b` | 5 | sí | `5e07f6df` | sí | aparentemente justificada, sin prueba |
| H_0346 | 2026-09-09 | `bx` | 10 | sí | `275161e9` | sí | aparentemente justificada, sin prueba |
| H_0368 | 2026-09-13 | `bf` | 13 | sí | `4e4ab1f3` | sí | aparentemente justificada, sin prueba |
| H_0379 | 2026-09-13 | `bf` | 7 | sí | `856b8e9e` | sí | aparentemente justificada, sin prueba |
| H_0386 | 2026-09-13 | `bf` | 6 | sí | `fbba5971` | sí | aparentemente justificada, sin prueba |
| H_0410 | 2026-09-13 | `b` | 5 | sí | `77967e2f` | sí | aparentemente justificada, sin prueba |
| H_0422 | 2026-09-13 | `bf` | 6 | sí | `7d55c2db` | sí | aparentemente justificada, sin prueba |
| H_0446 | 2026-09-14 | `bf` | 11 | sí | `1d82c9eb` | sí | aparentemente justificada, sin prueba |
| H_0449 | 2026-09-14 | `bx` | 4 | sí | `da543507` | sí | aparentemente justificada, sin prueba |
| H_0516 | 2026-09-14 | `b` | 4 | sí | `39743762` | sí | aparentemente justificada, sin prueba |
| H_0583 | 2026-09-15 | `bf` | 6 | sí | `65e3a965` | sí | aparentemente justificada, sin prueba |
| H_0586 | 2026-09-15 | `bx` | 5 | sí | `6fee2039` | sí | aparentemente justificada, sin prueba |
| H_0603 | 2026-09-15 | `b` | 1 | sí | `a6a52ef6` | sí | aparentemente justificada, sin prueba |
| H_0690 | 2026-09-15 | `bf` | 6 | sí | `—` | sí | aparentemente justificada, sin prueba |
| H_0705 | 2026-09-15 | `bf` | 7 | sí | `—` | sí | aparentemente justificada, sin prueba |
| **H_1015** | 2026-09-17 | `bf` | 6 | sí | `—` | **NO** | **sin justificación encontrada** |

**[C]** `H_0340` y `H_0341` comparten huella (`68ec36ea`). **Se mantienen como
dos registros independientes con identidad no determinable**, conforme al
criterio de esta fase.

### 3.1 Recuento por categoría

| categoría | n |
|---|---:|
| **Retirada justificada por evidencia verificable** | **0** |
| **Retirada aparentemente justificada, pero sin prueba suficiente** | **21** |
| **Retirada sin justificación encontrada** | **1** (`H_1015`) |
| **Caso indeterminado** (identidad) | 2 (`H_0340`, `H_0341`) |

**[D]** La categoría «retirada sin justificación» se aplica **solo a `H_1015`**,
porque no aparece en ninguna lista. **[D]** No significa que su retirada fuera
incorrecta: significa que **no se encontró ninguna razón registrada**. La
ausencia de justificación no prueba que la decisión fuera incorrecta.

---

## 4. Evidencia documental y técnica

### 4.1 Documental

| fuente | qué aporta |
|---|---|
| `DOCS/PROYECTO.md:733-735` | **[C]** la lista de 21 ids, atribuida a `pegar_9.txt` |
| `DOCS/PROYECTO.md:597-600` | **[C]** `H_0340` como ejemplo de «la ciega contada como open» |
| `DOCS/PROYECTO.md:726` | **[C]** `H_0342` y `H_0344` entre las «3 manos sin ganador registrado» |
| `DOCS/DEFECTO_214.md`, `RECONSTRUCCIONES_CM004.md` | **[C]** mencionan `H_0345` |
| `data/observations.json` | **[C]** 21 de 22; es artefacto derivado, no fuente |
| `SANEAMIENTO.md`, `CANAL_MANUAL_CERRADO.md`, `MIGRACION_CM001_CM003.md` | **[C]** 0 de 22 |
| `pegar_9.txt` (actual) | **[C]** 23 bytes, `eliminar H_1123, H_1188`; **no es la lista** |

### 4.2 Técnica

| comprobación | resultado |
|---|---|
| ¿algún script del commit puede borrar manos? | **[C] no** |
| ¿algún script nombra alguna de las 22? | **[C] no** |
| ¿las 52 modificaciones tienen firma de CM-004/CM-002? | **[C] sí, 39 de 52** |
| ¿algún criterio medible discrimina retiradas de permanentes? | **[C] no, de tres candidatos** |
| ¿`learn.py` en ese commit declara una exclusión que las contenga? | **[C] no**; `RELIABLE_HANDS = 900` es otro mecanismo |

### 4.3 Limitación de las pruebas

**[C]** `motor/test_rango_fiable.py` (nuevo en el commit) valida la «ventana
fiable» y `RELIABLE_HANDS = 900`. **[D]** **Ninguna prueba comprueba que el
número final de 1258 corresponda a un motivo.** El recuento es un efecto
secondary de una edición manual; no hay test que lo vincule a una regla, y por
eso el cambio pasó inadvertido.

---

## 5. Recomendación individual de conservación o recuperación

**[D]** Criterio de integridad, separado del estadístico: una mano no se
recupera porque cambie una métrica, ni se retira porque la cambie.

| id | recomendación | evidencia citada |
|---|---|---|
| `H_0340` | **mantener retirada** | **[C]** citada en la lista de `PROYECTO.md`; **[C]** identificada allí como «ejemplo de la inferencia errónea de subida» |
| `H_0341` | **decisión pendiente** | **[C]** citada en la lista; **[C]** huella idéntica a `H_0340` y **23 s** de diferencia: no se puede afirmar que sea otra mano |
| `H_0342`, `H_0344` | **decisión pendiente** | **[C]** citadas en la lista; **[C]** `PROYECTO.md:726` las registra como «sin ganador registrado» —rasgo observado, no motivo de retirada |
| `H_0339`, `H_0343`, `H_0345`–`H_0346` | **decisión pendiente** | **[C]** citadas en la lista; **[C]** ninguna fuente da el motivo |
| `H_0368`, `H_0379`, `H_0386`, `H_0410`, `H_0422`, `H_0446`, `H_0449`, `H_0516`, `H_0583`, `H_0586`, `H_0603`, `H_0690`, `H_0705` | **decisión pendiente** | **[C]** citadas en la lista; **[C]** ninguna fuente da el motivo |
| **`H_1015`** | **proponer recuperación** | **[C]** **no figura en ninguna lista documentada**; se retiró sin registro localisation |

**[D]** Solo `H_1015` tiene base para proponer recuperación, y la base es
precisa: **no está en la lista**, no porque su evidencia sea contraria, sino
porque **no hay ninguna**.

**[D]** Las 20 restantes se dejan **pendientes**, no «retiradas con fundamento»:
la lista demuestra que alguien las	decidió retirar, y nada más.

**[D]** Sobre las 22 en conjunto: **no se propone recuperarlas todas.** La
evidencia disponible es una lista sin razonamiento, y una lista sin
razonamiento no sostiene ni la retirada ni su reversión. Lo que sí sostiene es
**dejar la decisión documentada y abierta**, que es donde ya está.

---

## 6. Incertidumbres pendientes

| # | incertidumbre | por qué no se cierra |
|---|---|---|
| 1 | **El razonamiento tras la lista** | **[C]** no está en ningún fichero del repo |
| 2 | **El contenido de `pegar_9.txt` el 2026-10-14** | **[C]** el fichero fue rotado; su contenido actual es de otra lista |
| 3 | **Por qué se retiró `H_1015`** | **[C]** no figura en ninguna lista |
| 4 | **Si la lista de 21 es la de 20** | **[C]** la nota se contradice a sí misma |
| 5 | **Si `H_0340` y `H_0341` son dos manos** | **[C]** huella idéntica, 23 s de diferencia; el dato no decide |
| 6 | **Si la retirada fue correcta** | **[P]** requiere los fotogramas o el razonamiento del autor |
| 7 | **Quién editó el fichero a mano** | **[D]** el commit tiene un solo autor; no hay más traza |

**[D]** **No se atribuye intención al autor.** No hay evidencia documental ni
técnica que distinga «se-advirtió-que-estaban-mal» de «se-borraron-para-que-las
cifras-salian». Lo único comprobable es que la edición fue manual y no
documentada en el momento en que se hizo.

---

## 7. Verificación

**[M]** Los **ocho** hashes de fuentes, sin cambio:

| fuente | prefijo SHA-256 |
|---|---|
| `data/hands_db.jsonl` | `35727961646dfaba` **✓ esperado** |
| backup 1280 | `ec868e9305d1e03a` |
| `hands_db.jsonl.bak` | `032bc79c0a18988c` |
| `.antes_reinterpretacion` | `202a1f548fc60bac` |
| `antes_ciegas_…` | `35727961646dfaba` |
| `antes_sanear_…` | `31eba6e1c4824015` |
| `hands_db_old.jsonl` | `e7fbae80fe60e019` |
| flujo 84 | `9f1f61b53268df81` |

**[M]** Canónica: **1 782 206 bytes · 1258 líneas · SHA esperado**. **[M]** No se
modificó ninguna base, ni grabador, ni motor, ni pruebas. **[M]** No se
restauró ni eliminó ningún registro. **[M]** Modificado únicamente
`AUDITORIA_SEMANTICA_GRABADOR.md`. **[M] Ningún commit.**

**[D]** Nota de alcance: esta fase **no** modifica la clasificación de las
Partes IV y V más allá de corregir el error de documentación del § 2.3, y **no**
reabre la identidad de `H_0340`/`H_0341`.

---
---

# PARTE VII — POLÍTICA DE INTEGRIDAD HISTÓRICA Y ELEGIBILIDAD ANALÍTICA

Restricciones respetadas: sin modificar bases, sin restaurar ni eliminar
registros, sin tocar grabador, motor ni pruebas, **sin commit**. No se ejecutó
ninguna recuperación masiva. Esta parte es **una política y una arquitectura
propuesta**, no una versión nueva de la base.

---

## 1. Política de validez multidimensional

**[D]** La validez **no es una etiqueta**. Son **seis dimensiones
independientes**, y un registro puede ser apto para un análisis y no para otro.
Colapsarlas en «válida / inválida» es lo que permitió que una edición manual
pasara inadvertida (Parte VI).

### 1.1 Las seis dimensiones

| # | dimensión | pregunta | cómo se establece | admite «desconocido» |
|---|---|---|---|---|
| 1 | **Integridad estructural** | ¿se lee y cumple el esquema? | conteo de campos y tipos | no |
| 2 | **Consistencia interna** | ¿hay contradicciones verificables entre sus propios campos? | reglas de coherencia interna | no |
| 3 | **Fidelidad de captura** | ¿representa lo observado? | **captura original** | **sí, siempre** |
| 4 | **Semántica reconstruible** | ¿los campos monetarios tienen interpretación respaldada? | versión del grabador + fecha | **sí** |
| 5 | **Elegibilidad analítica** | ¿es apto para un análisis concreto? | **derivada de 1, 2 y 4** | no |
| 6 | **Procedencia** | ¿qué fuente, y con qué certeza? | registro de sesión y versión | **sí** |

**[D]** **Regla de no colapso:** ninguna dimensión absorbe a otra. Una mano
puede tener integridad estructural y **no** ser elegible para aportaciones
incrementales, y seguir siendo perfectamente útil para un análisis de
posiciones.

**[D]** **La dimensión 3 se declara `DESCONOCIDA` por defecto.** El JSONL no
conserva el fotograma, así que la fidelidad de captura **no es verificable con
los datos disponibles** para ningún registro, ni siquiera para los que nadie
ha cuestionado. Declararla «buena» sería inventar.

### 1.2 Lo que esta política NO permite

- **[D]** Excluir un registro de un análisis **sin un motivo escrito y
  reproducible**.
- **[D]** Borrar un registro porque produce un resultado incómodo. La
  ininconveniente no es un defecto de integridad: es una discrepancia
  estratégica, y se trata con filtros, no con eliminación.
- **[D]** Declarar inválida una mano por tener una acción reconstruida dudosa:
  eso afecta a **una acción**, no al registro.
- **[D]** Heredar una exclusión sin su motivo. `EXCLUSIONES_VENTANA_FABLE` es el
  ejemplo del problema: 23 ids con un comentario cuyo fundamento **el propio
  código declara falso**.

---

## 2. Evaluación individual de las 22 retiradas

**[C]** Medición sobre el estado en `02fc641`. Las columnas «pos. vacías»,
«pos. dup» y «huerf.» son **defectos verificables**, contados por separado:

- **pos. vacías**: jugadores sin posición asignada.
- **pos. dup**: **dos jugadores con la misma posición no vacía**.
- **huerf.**: acciones de una posición no declarada.

| id | estado en `02fc641` | estado en canónica | evidencia del motivo | estructura | contradicciones verificadas | semántica monetaria | elegibilidad | recomendación | falta para decidir |
|---|---|---|---|---|---|---|---|---|---|
| H_0339 | presente | **retirada** | **[C]** en la lista de `PROYECTO.md` | **[C]** OK | **[C]** ninguna | **[C]** W1, nivel | **[D]** apto para volumen; no para semántica fina | pendiente | el razonamiento de la lista |
| **H_0340** | presente | **retirada** | **[C]** en la lista; **[C]`PROYECTO.md:597` lo marca como «la ciega contada como open» | **[C]** OK | **[C]** ninguna | **[C]** W3, **indeterminada** | **[D]** **no** para aportaciones | **mantener retirada** (§ 3) | qué de la mano es erróneo y qué no |
| **H_0341** | presente | **retirada** | **[C]** en la lista | **[C]** OK | **[C]** ninguna | **[C]** W3, **indeterminada** | **[D]** **no** | **decisión pendiente** | si es otra mano (§ 4) |
| H_0342 | presente | **retirada** | **[C]** en la lista; **[C]** `PROYECTO.md:726` la registra «sin ganador registrado» | **[C]** OK | **[C]** 4 pos. vacías | **[C]** W3, **indeterminada** | **[D]** no | pendiente | el razonamiento de la lista |
| H_0343 | presente | **retirada** | **[C]** en la lista | **[C]** OK | **[C]** 2 pos. vacías | **[C]** W3, **indeterminada** | **[D]** no | pendiente | idem |
| H_0344 | presente | **retirada** | **[C]** en la lista; **[C]** «sin ganador registrado» | **[C]** OK | **[C]** ninguna | **[C]** W3, **indeterminada** | **[D]** no | pendiente | idem |
| H_0345 | presente | **retirada** | **[C]** en la lista | **[C]** OK | **[C]** ninguna | **[C]** W3, **indeterminada** | **[D]** no | pendiente | idem |
| H_0346 | presente | **retirada** | **[C]** en la lista | **[C]** OK | **[C]** 1 pos. vacía | **[C]** W3, **indeterminada** | **[D]** no | pendiente | idem |
| H_0368 | presente | **retirada** | **[C]** en la lista | **[C]** OK | **[C]** ninguna | **[C]** W4, delta puro | **[D]** apto con la fórmula de delta | pendiente | el razonamiento de la lista |
| **H_0379** | presente | **retirada** | **[C]** en la lista | **[C]** OK | **[C] 1 posición DUPLICADA (BTN×2) y 1 acción huérfana** | **[C]** W4, delta puro | **[D]** no para análisis de posición | pendiente | el razonamiento de la lista |
| H_0386 | presente | **retirada** | **[C]** en la lista | **[C]** OK | **[C]** ninguna | **[C]** W4, delta puro | **[D]** apto con la fórmula de delta | pendiente | el razonamiento de la lista |
| H_0410 | presente | **retirada** | **[C]** en la lista | **[C]** OK | **[C]** ninguna | **[C]** W4, delta puro | **[D]** apto con la fórmula de delta | pendiente | idem |
| H_0422 | presente | **retirada** | **[C]** en la lista | **[C]** OK | **[C]** ninguna | **[C]** W4, delta puro | **[D]** apto con la fórmula de delta | pendiente | idem |
| H_0446 | presente | **retirada** | **[C]** en la lista | **[C]** OK | **[C]** ninguna | **[C]** W4, delta puro | **[D]** apto con la fórmula de delta | pendiente | idem |
| H_0449 | presente | **retirada** | **[C]** en la lista | **[C]** OK | **[C]** ninguna | **[C]** W4, delta puro | **[D]** apto con la fórmula de delta | pendiente | idem |
| H_0516 | presente | **retirada** | **[C]** en la lista | **[C]** OK | **[C]** 2 pos. vacías | **[C]** W4, delta puro | **[D]** apto | pendiente | idem |
| H_0583 | presente | **retirada** | **[C]** en la lista | **[C]** OK | **[C]** ninguna | **[C]** W4, delta puro | **[D]** apto | pendiente | idem |
| H_0586 | presente | **retirada** | **[C]** en la lista | **[C]** OK | **[C]** 1 acción huérfana | **[C]** W4, delta puro | **[D]** apto | pendiente | idem |
| H_0603 | presente | **retirada** | **[C]** en la lista | **[C]** OK | **[C]** ninguna | **[C]** W4, delta puro | **[D]** apto | pendiente | idem |
| **H_0690** | presente | **retirada** | **[C]** en la lista | **[C]** OK | **[C] 1 posición DUPLICADA (MP×2)** | **[C]** W4, delta puro | **[D]** no para análisis de posición | pendiente | el razonamiento de la lista |
| H_0705 | presente | **retirada** | **[C]** en la lista | **[C]** OK | **[C]** ninguna | **[C]** W4, delta puro | **[D]** apto | pendiente | idem |
| **H_1015** | presente | **retirada** | **[C] NO figura en ninguna lista** | **[C]** OK | **[C]** ninguna | **[C]** W4, delta puro | **[D]** apto | **proponer recuperación** (§ 3) | si su retirada fue deliberada |

**[C]** Resumen: **22/22** con integridad estructural correcta. **20/22** sin
ninguna contradicción interna verificable. **7/22** en la ventana W3, cuya
semántica es indeterminada. **0/22** con importe no numérico.

### 2.1 Cuál es el único criterio que discrimina

**[C]** Se midieron cinco rasgos en las 22 y en las 1258 conservadas:

| rasgo | 22 retiradas | 1258 conservadas | discrimina |
|---|---:|---:|---|
| posiciones vacías | 12 (54,5 %) | 570 (45,3 %) | **no** |
| **posición duplicada** | **2 (9,1 %)** | **3 (0,2 %)** | **sí** |
| acción huérfana | 2 (9,1 %) | 7 (0,6 %) | parcialmente |
| importe no numérico | 0 | 0 | no |
| board con tamaño raro | 3 (13,6 %) | 676 (53,7 %) | **no, al revés** |

**[C]** Y el rasgo que más discrimina **no está dentro de la mano**: es la
**ventana**.

| ventana | antes | ahora | retiradas | % retirada |
|---|---:|---:|---:|---:|
| W1 (semántica de nivel) | 337 | 336 | 1 | **0,3 %** |
| **W3 (semántica INDETERMINADA)** | 25 | 18 | **7** | **28,0 %** |
| W4 (delta puro) | 918 | 904 | 14 | **1,5 %** |
| total | 1280 | 1258 | 22 | 1,7 % |

**[C]** La retirada se concentró **55 veces más** en la ventana cuya semántica
no se pudo determinar que en el resto de la base.

**[O]** Ese es el único hecho observado que separa las 22 del resto. **[D] No
es una justificación**: es una descripción de **qué** se retiró, no de **por
qué**. Que se retirara el 28 % de la ventana ambigua puede ser una decisión
razonada o una coincidencia. **El dato no lo decide**, y esta política no lo
convierte en una de las dos.

---

## 3. Tratamiento de `H_0340` y `H_1015`

### 3.1 `H_0340` — la inferencia no es el registro

**[C]** Lo que la documentación señala:

- `PROYECTO.md:597-600` la usa como ejemplo de `[('BB','b',1.0), ('UTG','f'), …]`
  donde «la ciega [queda] contada como *open*».
- `PROYECTO.md:735` la marca como «el ejemplo de la inferencia errónea de
  subida».

**[C]** Lo que esa observación **acierta**: la acción `BB b 1.0` es la ciega, y
el clasificador la trata como una apertura. Eso es un defecto del **motor de
clasificación**.

**[C]** Lo que **no** se ha establecido: que el resto del registro sea inválido.
La ficha de `H_0340` no tiene ninguna contradicción interna verificable, y su
semántica monetaria cae en W3, que es indeterminada para las 22 por igual.

**[D]** **Son dos cuestiones distintas y la política las separa:**

| | dimensión afectada | veredicto |
|---|---|---|
| «la ciega se cuenta como subida» | **una acción** y **el clasificador** | **[C] defecto demostrado**, afecta a W1, W3 y W4 por igual |
| «el registro `H_0340` es inválido» | **el registro entero** | **[D] sin evidencia** |

**[D]** **Recomendación: mantener retirada, por el motivo equivocado.** No
porque la inferencia sea errónea —que lo es— sino porque está en la ventana
W3 y su semántica es indeterminada. **[D]** Si algún día se recupera la mano
**por su contenido**, el defecto del clasificador seguirá existiendo y habrá que
corregirlo **en el motor**, no en el registro.

### 3.2 `H_1015` — ausente de la lista, no(superar) la conclusión

**[C]** `H_1015` **no figura en la lista de `PROYECTO.md`** ni en ninguna otra
fuente localizada. Fue retirada y no aparece en ninguna instrucción.

**[C]** Su ficha no tiene ninguna contradicción interna verificable, y su
semántica es la de W4 (delta puro), que sí está delimitada.

**[D]** Lo que **no** se infiere: que su retirada fuera accidental. **[D]** Lo
que tampoco se infiere: que fuera deliberada. **La ausencia de registro es una
ausencia de registro**, y no distingue entre las dos hipótesis.

**[D]** **Recomendación: proponer recuperación**, por dos razones
separables:

1. **[C]** No hay ninguna instrucción que la retirer.
2. **[C]** Semánticamente es una de las manos **más utilizables** de las 22:
   está en W4 y no tiene defectos internos.

**[D]** La recuperación sería una **decisión**, no una reparación: depende de si
el criterio de `75bbdb7` se considera válido en conjunto. Si resulta que sí,
`H_1015` cae dentro de él implícitamente aunque no estuviera en la lista.

---

## 4. Las otras 20: por qué «pendiente» y no «retirada»

**[D]** Para 20 de las 22 hay una lista que las menciona. **La lista no es un
razonamiento.** Lo único que la sostiene es que alguien las escribió en ella.

**[D]** Propuesta de estados, y por qué:

| estado |_records_ | condición |
|---|---:|---|
| **RETIRADA-JUSTIFICADA** | 0 | criterio verificable, individual, escrito |
| RETIRADA-PENDIENTE | 21 | hay lista, no hay criterio. Estado **abierto**, no «definitivo» |
| RETIRADA-SIN-TRAZA | 1 (`H_1015`) | no hay lista |
| **INDETERMINADA-IDENTIDAD** | 2 (`H_0340`/`H_0341`) | huella idéntica, 23 s de diferencia |

**[D]** `RETIRADA-PENDIENTE` es una categoría **nueva y deliberada**: el registro
está fuera de la base operativa, **pero su situación no está resuelta**, y el
motivo no es heredable. Se propone para evitar que una retirada sin
razonamiento se convierta en tradición y acabe pareciendo justificada.

---

## 5. Tratamiento de registros corregidos

**[P]** Arquitectura propuesta. **No implementada.**

### 5.1 Cinco estados, no uno

| estado | qué es | se conserva el original |
|---|---|---|
| **OBSERVADO** | lo que el grabador escribió en su momento | sí, siempre |
| **INTERPRETADO** | una lectura derivada de lo observado, con regla y versión | sí |
| **CORREGIDO** | cambio aplicado **con evidencia citada** | sí, junto al anterior |
| **EXCLUIDO** | no entra en un análisis concreto, **con motivo y ámbito** | sí |
| **RETIRADO** | fuera de la base operativa, **con motivo y decisión** | sí, en el histórico |

**[P]** Los cinco son **no excluyentes**: un registro puede ser `OBSERVADO` +
`CORREGIDO` + `EXCLUIDO` de un análisis y `OBSERVADO` + `CORREGIDO` + `ELEGIBLE`
para otro.

### 5.2 Trazabilidad mínima de una corrección

```json
{
  "hand_uid": "…",
  "revision": 3,
  "campo": "streets.preflop.actions[0].action",
  "antes": "b", "despues": "r",
  "regla": "CM-004",
  "evidencia": "sha256:…",
  "proceso": "tools/aplicar_reinterpretacion.py@bb60aa8",
  "fecha": "2026-10-14T15:55:53",
  "autor": "script"
}
```

**[P]** Regla dura: **ningún campo se sobrescribe en silencio.** Toda
diferencia entre la revisión *n* y la *n−1* tiene una entrada con regla,
evidencia, proceso y fecha. **[P]** Si no hay evidencia, el estado es
`INTERPRETADO`, no `CORREGIDO`.

**[P]** Una hipótesis nunca se escribe como observación. Si una corrección es
probable pero no verificada, se marca `INTERPRETADO` y **no entra** en los
análisis que exijan `OBSERVADO`.

### 5.3 Corregir `H_0340` sería un error de categoría

**[D]** El defecto de `H_0340` está en el **motor de clasificación** que
interpreta la acción, no en el dato. **[P]** Si se corrigiera, se corregiría el
clasificador, y el registro se dejaría intacto.

---

## 6. Las dos alternativas de almacenamiento

### 6.1 Alternativa A — base operativa + histórico inmutable

**[D]** `data/hands_db.jsonl` es la base de trabajo; el histórico completo vive
en un archivo aparte, de solo lectura.

| | |
|---|---|
| **ventajas** | **[D]** el motor lee un fichero limpio; **[D]** el histórico no se toca nunca; **[D]** migrations complejas como la actual |
| **limitaciones** | **[C] ninguna de las 1258 dice de dónde salió**; **[D]** toda exclusión debe vivir en el código (`EXCLUSIONES_VENTANA_FABLE`) — que es exactamente donde el proyecto ya se ha equivocado |
| **riesgo** | **[D]** el histórico y la operativa se **desincronizan sin que nada lo diga**. Ya ocurrió: el backup de 1280 y el fichero de git tienen contenidos distintos |
| **consecuencia** | **[D]** las 22 withdrawn no quedan en ningún sitio legible sin el histórico |

### 6.2 Alternativa B — conjunto íntegro + filtros versionados

**[D]** Un histórico inmutable y completo; cada análisis declara su población
mediante un filtro versionado.

| | |
|---|---|
| **ventajas** | **[D]** nada se pierde: **toda** mano existe y es elegible o no por filtro; **[D]** el motivo de cada exclusión queda junto a la exclusión; **[D]** una mano puede entrar en un análisis y salir de otro sin tocar datos |
| **limitaciones** | **[P]** hay que convertir `load_hands()` en un lector con filtros; **[D]** el rendimiento empeora si no se cachea; **[D]** obliga a declarar la población de cada métrica, lo que es trabajo |
| **riesgo** | **[D]** **duplicación**: los derivados actuales están construidos sobre la base ya filtrada. Cambiar a B invalidaría todo lo derivado |
| **consecuencia** | **[D]** es la opción que hace imposible repetir el error de `75bbdb7` |

### 6.3 Comparación

| criterio | A | B |
|---|---|---|
| integridad | **[D]** depende de que nadie edite la operativa | **[D]** fuerte: el histórico no se edita por definición |
| trazabilidad de exclusiones | **[D]** en el código, dispersa | **[D]** junto al filtro, versionada |
| coste de migración | **[D]** bajo | **[D]** alto: todos los derivados |
| riesgo de que un registro desaparezca | **[D]** alto — ya pasó | **[D]** nulo |
| motores existentes | **[D]** siguen funcionando | **[D]** hay que tocar `learn.load_hands` |

### 6.4 Recomendación

**[D] Alternativa B**, y la razón es concreta: **[C] el incidente que motivó
esta auditoría ocurrió porque no había forma de registrar «esta mano está
fuera y por qué» sin borrar la mano.** **[C]** Con B, las 22 habrían seguido
en el histórico, con su filtro y su motivo, y el criterio de `75bbdb7` sería
revisable.

**[D]** B **no es gratis**: **[P]** invalidaría `observations.json`,
`behavior.json`, `preflop_matrices.json` y `profile_ranges.json`, que están
construidos sobre la base ya filtrada. **[D]** La secuencia sensata es:

1. **[D]** Congelar la base actual como **versión 0** del histórico, sin
   cambiar nada.
2. **[P]** Construir la B sobre ella, **recuperando** las 22 de `02fc641` en
   el histórico, **no** en la operativa.
3. **[P]** Declarar cada métrica con su filtro.
4. **[D]** Recién entonces, regenerar derivados.

**[D]** Los pasos 2 a 4 **no se ejecutan en esta fase.**

---

## 7. Qué debe significar cada recuento

**[D]** **1258 no es un objetivo.** Es el número de la versión actual de la base.
La política obliga a publicarlo descompuesto:

| recuento | definición | valor actual |
|---|---|---:|
| **R1 · registros físicos** | líneas del fichero | **1258** |
| **R2 · estructuralmente válidos** | R1 menos los que no parsean o no cumplen esquema | **1258** |
| **R3 · identidad establecida** | R2 con identidad global confirmada | **0** |
| **R4 · elegibles por análisis** | depende de la métrica | **se declara por análisis** |
| **R5 · retirados** | fuera de la base operativa | **22** |
| **R6 · excluidos de un análisis** | dentro de la base, fuera de una métrica | **varios, por `EXCLUSIONES_VENTANA_FABLE`** |
| **R7 · pendientes** | situación no resuelta | **21** |

**[C]** **R3 = 0 es el dato más importante de esta tabla.** No existe ni una
sola mano con identidad global confirmada, porque `hand_id` colisiona entre
ficheros (Parte V) y se reconstruye al arrancar.

**[P]** **Regla de publicación:** ninguna cifra se emite sin los siete
recuentos que la delimitan. Un «5433 aportaciones calculables» sin decir R4,
R5 y R6 no es interpretable.

**[D]** **1258 no debe conservarse por ser 1258.** Si el filtro correcto deja
fuera 40 manos, el número correcto será 1218 y eso será un éxito, no un fallo.

---

## 8. Pruebas de integridad propuestas

**[P]** No implementadas. Cada una nombra **qué evidencia independiente la
validaría**, porque una prueba que recalcula lo mismo no vale.

| # | prueba | evidencia independiente |
|---|---|---|
| 1 | **Ninguna mano pierde `hand_id` sin entrada de trazabilidad** | el registro de decisiones: motivo, fecha, autor |
| 2 | **Todo registro es parseable y cumple el esquema** | **[C]** hoy es cierto: 1258/1258 |
| 3 | **Ninguna acción referencia una posición no declarada** | hoy: 7 de 1258 lo hacen → **fallaría**, y por tanto vale |
| 4 | **Ninguna posición aparece en dos jugadores** | hoy: 3 de 1258 → **fallaría** |
| 5 | **`amount` nunca se lee sin `amount_type`** | **[C]** hoy 0 de 13826 tienen `amount_type` → **fallaría** |
| 6 | **El histórico y la operativa declaran su diferencia** | una lista de.hand_ids retirada, con motivo por registro |
| 7 | **Cada exclusión tiene motivo vigente y vigente en el código** | **[C]** hoy el motivo de `EXCLUSIONES_VENTANA_FABLE` **está declarado falso por el propio código** → fallaría |
| 8 | **Toda métrica declara su población** | el recuento R4 junto al resultado |
| 9 | **Ninguna cifra de aportación se publica sin ventana** | el campo `ventana` en el informe |
| 10 | **El SHA del histórico cambia cuando cambia la operativa** | dos hashes distintos, verificables |

**[D]** **[C] Cuatro de estas diez fallarían hoy.** Se proponen **precisamente
por eso**: un conjunto de pruebas que todo pasa no prueba nada, y el
incidente que motivó la auditoría habría sido detectado por la prueba 6.

---

## 9. Decisiones que requieren aprobación explícita

**[D]** Ninguna se toma en esta fase.

| # | decisión | alternativa | consecuencia de no decidir |
|---|---|---|---|
| 1 | **¿Alternativa A o B?** | seguir con A | se repite la posibilidad de editar la base sin rastro |
| 2 | **¿Se recuperan las 22?** | mantenerlas fuera | las 22 siguen sin identidad verificable |
| 3 | **¿`H_1015` se recupera aunque el criterio siga sin conocer?** | mantenerla fuera | se pierde una mano de W4 sin contradicciones |
| 4 | **¿Se declara `RETIRADA-PENDIENTE` como estado nuevo?** | no declararlo | la situación sigue abierta sin nombre |
| 5 | **¿Se congela la base actual como versión 0?** | no congelar | no hay punto de retorno verificable |
| 6 | **¿Cuándo se regeneran los derivados?** | nunca | los derivados actuales siguen siendo irreconciliables |
| 7 | **¿Se implementan las 10 pruebas de integridad?** | no | las cuatro que fallarían siguen sin detectar |
| 8 | **¿Quién decide sobre `H_0340`/`H_0341`?** | nadie | dos registros idénticos sin resoler |

**[D]** La 3 es la única que esta fase **recomienda** y que **no**
propone ejecutar: el resto son preparatorias.

---

## 10. Verificación

**[M]** Las **ocho** fuentes conservan su hash:

| fuente | prefijo SHA-256 |
|---|---|
| `data/hands_db.jsonl` | `35727961646dfaba` **✓ esperado** |
| backup 1280 | `ec868e9305d1e03a` |
| `hands_db.jsonl.bak` | `032bc79c0a18988c` |
| `.antes_reinterpretacion` | `202a1f548fc60bac` |
| `antes_ciegas_…` | `35727961646dfaba` |
| `antes_sanear_…` | `31eba6e1c4824015` |
| `hands_db_old.jsonl` | `e7fbae80fe60e019` |
| flujo 84 | `9f1f61b53268df81` |

**[M]** Canónica: **1 782 206 bytes · 1258 líneas · SHA esperado**.
**[M]** No se modificó ninguna base; no se restauró ni eliminó ningún registro;
no se tocó grabador, motor ni pruebas. **[M]** Modificado únicamente
`AUDITORIA_SEMANTICA_GRABADOR.md`. **[M] Ningún commit.**

### 10.1 Corrección registrada

**[C]** La primera medición de esta fasecontuvo un defecto en mi propia
comprobación: contaba las **posiciones vacías** como duplicadas, y por eso
reportaba 14 de 22 con «posiciones repetidas». **[C]** Corregida: solo **2 de
22** tienen posición **realmente** duplicada (`H_0379`, `H_0690`). **[D]** La
tabla del § 2 usa la comprobación correcta.

### 10.2 Limitaciones

**[D]** La dimensión **fidelidad de captura** es `DESCONOCIDA` para las 1258
manos: sin los fotogramas no hay forma de establecerla para ninguna.

**[D]** El por qué de `75bbdb7` sigue sin determinarse. Esta fase **[D] no lo
resuelve**: lo acota, muestra que la retirada se concentró en la ventana
ambigua, y propone el estado que hace esa ambigüedad explícita.

---
---

# PARTE VIII — DISEÑO DE MIGRACIÓN AL HISTÓRICO ÍNTEGRO

Fase **exclusivamente de diseño e inventario**. No se ejecutó la migración, no
se recuperó nada, no se modificó ningún dato, código ni prueba, y **no hubo
commit**.

## 0. Estado del repositorio, registrado antes de inspeccionar

**[C]** Al **inicio** de esta fase:

| | |
|---|---|
| `HEAD` | **`1dda6aa`** — «A2 la puerta de `ejecutar_pytest` era única en dos ficheros de quince» |
| `HEAD~1` | `b786e3b` — «A1: resuelve el merge con `origin/main`…» (commit mío, fase anterior) |
| rama | `main`, **al día con `origin/main`** |
| staged | ninguno |
| unstaged | `REVISION_DIAGNOSTICO_GRABADOR.md` (+16) |
| untracked | `AUDITORIA_SEMANTICA_GRABADOR.md` |

**[C]** `1dda6aa` es **externo a esta tarea**. **[D]** Este diseño se apoya en
ese estado y no asume que el árbol siga como en la Fase VII.

**[C]** Al **final** de esta fase: `HEAD` sin cambios, staged vacío, y solo los
dos ficheros de auditoría modificados. **No se tocó ningún cambio ajeno.**

---

## 1. Especificación de la versión 0

**[D]** La versión 0 es **una referencia inmutable a la base canónica actual**.
No se crea ningún fichero nuevo: es el estado existente,-described.

### 1.1 Metadatos de la versión 0

```yaml
version_0:
  ref:            "data/hands_db.jsonl"
  sha256:         "35727961646dfaba2c67fd5ee0dbe9b0669d3156f9c6f3fa3585060a93f097e2"
  bytes:          1782206
  registros:      1258
  lineas_validas: 1258
  lineas_ilegibles: 0
  git_commit:     "33ab8ee"
  esquema:
    mano:     [hand_id, date, btn_idx, btn_player, players, comunitarias,
                streets, final_pot, showdown, winner, allin]
    accion:   [pos, action, amount, inferred]
    # `allin` ausente en 73; `inferred` presente en 23
  created:        "2026-10-16T18:53:36-05:00"   # commit que la dejó así
  referencia:     "2026-10-18"                   # fecha de esta referencia
```

### 1.2 Fuentes conocidas de la versión 0

**[C]** Se inventario **antes** de congelar, para que la versión 0 no se
defina contra un conjunto de fuentes que después cambia:

| fuente | SHA-256 (prefijo) | registros | relación |
|---|---|---:|---|
| `data/hands_db.jsonl` | `35727961646dfaba` | 1258 | **la propia v0** |
| `_backup_aplicar_correcciones/hands_db.jsonl` | `ec868e9305d1e03a` | 1280 | **NO** es el predecesor |
| git `02fc641` | `173a7274` | 1280 | **sí** es el predecesor inmediato |
| git `75bbdb7` | `7d972b2b` | 1258 | retirada de 22 |
| `recorder/hands_db_old.jsonl` | `e7fbae80fe60e019` | 668 | flujo anterior, 268 contenidos comunes |
| `recorder/hands_db.jsonl` | `9f1f61b53268df81` | 84 | **disjunto**, 0 contenidos comunes |

### 1.3 Incertidumbres que la v0 DEBE declarar

**[C]** La versión 0 **no** declara reliability. Declara límites:

| incertidumbre | valor |
|---|---|
| identidad global confirmada | **0 de 1258** |
| procedencia confirmada | **0 de 1258**; temporal probable en todas |
| semántica de `amount` confirmada por mano | **0** |
| manos con `amount_type` | **0 de 13826** |
| manos en ventana de semántica indeterminada | 18 |
| registros con presencia de duplicado conocido | 1 contenido, 2 registros |
| fidelidad de captura verificable | **no verificable** para ninguna |

**[D]** **`hand_id` NO es identidad global** y la v0 lo dice explícitamente:
colisiona entre ficheros (84/84 en el flujo secundario) y se reconstruye al
arrancar (`_ensure_hand_id`).

### 1.4 Lo que la v0 **no** afirma

**[D]** No afirma contener todo el historial. No afirma que sus 1258 manos sean
fieles. No afirma que 1258 sea el número correcto. **[D]** Afirma exactamente
cuántos bytes hay y qué hash tienen.

### 1.5 Preservación de las fuentes sin sobrescribir

**[D]** Reglas:

1. **[P]** La v0 **no se copia a ningún sitio nuevo** mientras siga siendo la
   base operativa. Duplicarla hoy crearía dos fuentes de verdad.
2. **[P]** Cuando la v0 deje de ser la operativa, se copia **con su hash como
   nombre**, y el original **no se borra**: se marca `retirada`.
3. **[P]** Los backups y los ficheros laterales se **catalogan, no se tocan**.
   Su SHA se registra en un manifiesto; si cambia, es un hecho nuevo y no una
   sobrescritura silenciosa.
4. **[C]** `hands_db.jsonl.bak` **ya está desalineado** de la v0 en 3
   contenidos. **[D]** Es un ejemplo de por qué la regla 3 es necesaria.

---

## 2. Inventario de derivados

**[C]** 12 artefactos JSON en `data/`. **Solo 2 tienen sello de procedencia.**

| artefacto | bytes | último commit | `meta` | clasificación |
|---|---:|---|---|---|
| `observations.json` | 4 896 333 | 2026-10-15 | **NO** | **no reproducible** |
| `behavior.json` | 27 550 | 2026-10-15 | **NO** | **no reproducible** |
| `preflop_matrices.json` | 328 548 | 2026-10-14 | **NO** | **no reproducible** |
| `preflop_stats.json` | 149 053 | 2026-10-15 | **NO** | **no reproducible** |
| `player_stats.json` | 88 573 | 2026-10-15 | **NO** | **no reproducible** |
| `profile_ranges.json` | 93 649 | 2026-10-15 | **SÍ** | **con limitaciones** |
| `postflop_ranges.json` | 13 203 | 2026-10-15 | **SÍ** | **con limitaciones** |
| `profiles.json` | 78 020 | 2026-10-15 | **NO** | **no reproducible** |
| `behavior_probs.json` | 18 133 | 2026-10-14 | **NO** | **no reproducible** |
| `golden.json` | 37 161 | 2026-10-14 | **NO** | no aplica (golden de test) |
| `db_health.json` | 6 151 | 2026-10-14 | **NO** | pendiente |
| `calib_1365.json` | 1 353 | 2026-08-12 | **NO** | no aplica (calibración OCR) |

### 2.1 Lo que el sello existente dice

**[C]** `motor/_procedencia.py` (111 líneas) ya existe y documenta
`hands_input`, `hands_used`, `hands_window`, `code_commit`, `arbol_sucio` y
`RUTAS_RELEVANTES`. Sus valores actuales:

| derivado | `hands_input` | `hands_used` | `hands_window` | `code_commit` | `arbol_sucio` |
|---|---:|---:|---|---|---|
| `profile_ranges.json` | 877 | 863 | `reliable_only` | `8e527c3` | **True** |
| `postflop_ranges.json` | 877 | 875 | `reliable_only` | `8e527c3` | **True** |

**[C]** `8e527c3` **existe** (2026-10-15 18:42:50). **[C]** Pero
`arbol_sucio: True` significa que se construyeron con cambios **sin commitear**.

**[D] Ninguno de los 12 derivados es reproducible con evidencia suficiente.**
Los dos sellados son **reproducibles con limitaciones**, y su limitación es
declarada por el propio sello. Los otros 10 **no son reproducibles**: no se
sabe con qué población ni con qué versión del código se hicieron.

**[C]** `observations.json` contiene **9250** observaciones. **[C]** La nota de
`PROYECTO.md` que citaba 3373 **está desactualizada**: el fichero cambió.

### 2.2 Riesgo por artefacto al aplicar filtros

| artefacto | riesgo | por qué |
|---|---|---|
| `observations.json` | **alto** | **[C]** es el más grande y el más dependiente de población; sin `meta` no se puede saber cuál usou |
| `profile_ranges.json`, `postflop_ranges.json` | **medio** | **[C]** declaran `hands_input: 877`, que **no es 1258**: ya aplican `reliable_only`. **[D]** Son el precedente más útil: ya son «población + sello» |
| `preflop_matrices.json` | **medio** | **[C]** es **fuente** para `preflop.py`, `profile.py` y `player_ranges`; cambiar la base lo invalida |
| `behavior*.json`, `preflop_stats.json`, `player_stats.json`, `profiles.json` | **alto** | **[C]** sin `meta`; imposible saber su población |

**[D]** El proyecto **ya tiene el patrón** que la fase VII propuso: población +
sello, en `profile_ranges.json`. **[D]** La arquitectura B no es una invención:
es **generalizar lo que ya hacen dos ficheros**.

---

## 3. Modelo propuesto de identidad

**[P]** Propuesta. **No implementada.**

### 3.1 Los cinco identificadores

| # | identificador | qué identifica | ¿estable? |
|---|---|---|---|
| 1 | **`record_uid`** | el registro físico tal como se escribió | **sí**, si se define como hash del contenido literal + fichero |
| 2 | **`session_id`** | la ejecución del grabador | sí, con fecha y ruta de salida |
| 3 | **`local_seq`** | el índice dentro del fichero | sí, y **solo dentro** del fichero |
| 4 | **`event_uid`** | la mano de póquer real | **no siempre construible** |
| 5 | **`equivalencia`** | la relación entre registros | **con nivel de certeza** |

**[P]** Definiciones:

```
record_uid  = sha256("v0" | source_sha256 | line_no)
             → estable, no depende de hand_id, no colisiona entre ficheros

session_id  = ISO-8601 de la sesión + ruta de salida del grabador
             p.ej. "2026-09-13T19:46:52/data/hands_db.jsonl"

local_seq   = hand_id DENTRO de ese session_id
             → nunca global

event_uid   = sha256("ev" | session_id | detector_frame_seq)
             → construible SOLO si existe un identificador de fotograma,
               que hoy NO existe  ⇒  event_uid = null para las 1258
```

**[D]** **`event_uid` es `null` para las 1258 manos.** No se puede construir
una identidad de evento sin un identificador de fotograma, y el grabador no lo
escribe. **[P]** Es el hueco de datos más importante que queda abierto.

### 3.2 La huella de contenido: qué es y qué no es

**[P]** `content_fp = sha256(registro sin {hand_id, date})`

| | |
|---|---|
| **[P]** sirve para | localizar candidatas, agrupar y detectar cambios |
| **[P]** **no** sirve para | **probar identidad de evento** |

**[D]** `H_0340` y `H_0341` tienen `content_fp` idéntico y **23 s** de
diferencia. **[D]** El dato admite dos lecturas y no decide: dos manos con el
mismo desarrollo, o un evento escrito dos veces. **[P]** Se modelan como:

```json
{
  "record_uid": "…A", "local_seq": "H_0340", "session_id": "…",
  "content_fp": "68ec36ea…",
  "event_uid": null,
  "equivalencia": [
    {"con": "record_uid:…B", "tipo": "posible_duplicado",
     "certeza": "INDETERMINADA", "base": "content_fp identico + 23 s"}
  ]
}
```

**[P]** Regla dura: **dos registros con `content_fp` idéntico NO se fusionan.**
Solo se fusionan si alguna vez se añade un `event_uid` real.

### 3.3 Registros corregidos

**[P]** Una corrección **no cambia el `record_uid`**: crea una revisión.

```json
{
  "record_uid": "v0|sha|lin",
  "revision": 2,
  "estado": "OBSERVADO",
  "observado": { "…" : "valor literal en la v0" },
  "anotaciones": [ … ],
  "derivado": { "…" : "lo que el análisis usa" }
}
```

**[P]** El campo `derivado` nunca se escribe dentro del histórico: se calcula,
y su valor queda atado al `filtro_version` que lo produjo.

---

## 4. Capa de anotaciones y correcciones

**[P]** Estructura propuesta, **sin tocar el original**:

```json
{
  "record_uid": "v0|sha|lin",
  "campo": "streets.preflop.actions[0].action",
  "valor_original": "b",
  "valor_derivado": "r",

  "tipo": "CORRECCION",
  "regla": "CM-004",
  "regla_version": "1.0",
  "evidencia": {"tipo": "test_o_captura", "ref": "sha256:…"},
  "proceso": "tools/aplicar_reinterpretacion.py",
  "commit": "bb60aa8",
  "fecha": "2026-10-14T15:55:53",
  "autor": "script",

  "estado": "REVISADA",
  "revisada_por": null,
  "revisada_fecha": null
}
```

### 4.1 Corrección vs hipótesis

**[D]** La distinción es la línea roja de esta capa:

| tipo | requiere | se usa en |
|---|---|---|
| `CORRECCION` | **evidencia citada** (captura, test, SHA) | métricas |
| `REINTERPRETACION` | regla y versión, **sin evidencia directa** | solo análisis que lo admita |
| `HIPOTESIS` | nada más que un razonamiento | **ninguno** |

**[P]** `H_0340` sería **`REINTERPRETACION`**, no `CORRECCION`: la ciega contada
como subida es un defecto **del clasificador**, y su correccion seria un
cambio en el motor, no una anotación sobre el registro.

### 4.2 Anotaciones reversibles

**[P]** Una anotación se retira **borrando la anotación**, nunca el registro.
**[P]** El histórico **nunca** guarda el valor corregido como si fuera el
original: `valor_original` es inmutable y `valor_derivado` se recalcula.

---

## 5. Filtros analíticos versionados

**[P]** Un filtro es un **fichero declarativo versionado**, no código.

```json
{
  "filtro_version": "aportes_incrementales@1.0.0",
  "creado": "2026-10-18",
  "entrada": {"version_0": "sha256:35727961646dfaba…",
              "poblacion_ref": "poblaciones/operativa.json"},

  "reglas": [
    {"id": "ventana-semantica",
     "desc": "excluye las manos cuya semantica de `amount` es indeterminada",
     "aplica_a": "W3",
     "motivo": "el cambio de implementacion cae dentro de esta ventana",
     "certeza": "PROBADA"},
    {"id": "sin-marca-amount-type",
     "desc": "todo lo anterior, pendiente de resolver",
     "aplica_a": "*",
     "motivo": "0 de 13826 acciones tienen amount_type",
     "certeza": "PROBADA"}
  ],

  "cobertura": {"entrada": 1258, "incluidas": 1223, "excluidas": 35},
  "incertidumbres": [
    "ninguna mano tiene identidad de evento establecida",
    "la version 0 no declara fiabilidad"
  ]
}
```

### 5.1 Reglas de diseño

**[D]** **La elegibilidad es específica del análisis.** El filtro
`aportes_incrementales` puede excluir 35 manos por semántica indeterminada
mientras un filtro `conteo_acciones` las incluye todas: ninguna de las dos
poblaciones está equivocada, son preguntas distintas.

**[P]** Cada exclusión necesita **motivo por registro**, no solo por regla:

```json
{"record_uid": "…", "excluido_por": "ventana-semantica", "motivo": "…"}
```

**[P]** Un filtro **no puede** fijar un número. Si su cobertura cambia sin cambiar
su versión, es un fallo del filtro.

---

## 6. Plan de tratamiento de las 22 retiradas

**[P]** Sin ejecutar. La incorporación al histórico **no** las devuelve a la
base operativa.

### 6.1 Las cuatro magnitudes, separadas

**[C]** Al añadirlas al histórico habría que registrar, por separado:

| magnitud | valor |
|---|---:|
| registros del predecesor ausentes de la v0 | **22** |
| contenidos distintos entre ellos | **21** |
| registros con identidad de evento establecida | **0** |
| equivalencias declaradas | 1, con certeza `INDETERMINADA` |

**[P]** Las 22 entran como **`OBSERVADO`**, con `estado_historico:
RETIRADA_PENDIENTE` (21) o `RETIRADA_SIN_TRAZA` (`H_1015`). **[P]** Ninguna
entra como elegible hasta que se apruebe el filtro correspondiente.

### 6.2 `H_0340` y `H_1015`, por separado

| | `H_0340` | `H_1015` |
|---|---|---|
| **1. Estado histórico** | retirado en `75bbdb7`; en la lista de `PROYECTO.md` | retirado en `75bbdb7`; **no figura en ninguna lista** |
| **2. Evidencia** | **[C]** listada; **[C]** marcada como «ejemplo de la inferencia errónea de subida» | **[C]** ninguna instrucción |
| **3. Integridad** | **[C]** estructura OK, sin contradicciones internas | **[C]** estructura OK, sin contradicciones internas |
| **4. Semántica** | **[C]** W3, **indeterminada** | **[C]** W4, **delta puro delimitado** |
| **5. Elegibilidad** | **[D]** no para aportaciones | **[D]** apto con la fórmula de delta |
| **6. Propuesta** | añadir al histórico como `RETIRADA_PENDIENTE`; **no** tocar el clasificador | añadir al histórico como `RETIRADA_SIN_TRAZA`; **proponer recuperación operativa** |
| **7. Decisión requerida** | ¿se mantiene retirada? | ¿se recupera a la operativa? |

**[D]** En `H_0340` la cuestión es **doble** y no debe fusionarse: el defecto
de la inferencia **es del motor** y seguirá existiendo recupere o no la mano.

---

## 7. Evaluación de compatibilidad

**[C]** Inventario de consumidores: **66 ficheros** mencionan
`hands_db.jsonl`. **16 procesos** escriben o respaldan la base.

### 7.1 Puntos de fricción

| riesgo | consumidor | evidencia |
|---|---|---|
| **lee `hands_db.jsonl` directamente** | `motor/learn.py`, `motor/db_health.py`, `motor/preflop.py`, `hand_editor.py`, `tools/*` | **[C]** 66 ficheros |
| **asume `hand_id` único** | `motor/test_auc_integridad.py:38` | **[C]** `assert len(ids) == len(set(ids))` |
| **usa `hand_id` como clave** | **[C]** 19 sitios, p.ej. `motor/test_multiway.py:403` | **[C]** dict por `hand_id` |
| **escribe o reinterpreta** | **[C]** 16 procesos, p.ej. `tools/aplicar_reinterpretacion.py`, `tools/sanear_base.py` | **[C]** |
| **cuenta con `RELIABLE_HANDS = 900`** | `motor/learn.py` | **[C]** constante |

**[C]** **Cero aserciones de unicidad explícitas** salvo la de
`test_auc_integridad.py`. **[D]** Los demás usos son lookups por clave, que
seguirían funcionando mientras no se mezclen ficheros.

### 7.2 Transición compatible y reversible

**[P]** Punto de intervención único:

```python
# motor/identidad.py  (NUEVO)
def cargar(version_0_sha=None, filtro=None) -> Poblacion:
    ...
```

**[P]** Reglas de la transición:

1. **[P]** `learn.load_hands()` **conserva su firma**. Por debajo cambia el
   lector. **[D]** Es el único punto que hay que tocar en el motor.
2. **[P]** La v0 se sirve **igual** que hoy: 1258 registros, mismo hash. **[D]**
   Nada cambia para el análisis hasta que se apruebe un filtro.
3. **[P]** Los procesos que **escriben** pasan a **escribir en el histórico**,
   nunca en la operativa.
4. **[P]** **Reversión**: basta con que `version_0_sha` apunte al hash
   anterior. **[D]** No hay que deshacer nada, porque nada se reescribe.

**[D]** **Riesgo de doble conteo.** **[C]** Hoy, 268 contenidos de
`hands_db_old.jsonl` coinciden con la canónica. **[P]** Si el histórico
absorbe ese fichero **y** la operativa, esas 268 se contarían dos veces. **[P]**
Por eso el histórico se indexa por `record_uid` —**que incluye el hash del
fichero de origen**— y nunca por `content_fp`.

---

## 8. Plan de pruebas de integridad

**[P]** Las diez de la Parte VII,que ampliadas. **No implementadas.**

| # | invariante | evidencia independiente | **hoy** | qué detectaría | depende de | ¿tautológica? | aceptación |
|---|---|---|---|---|---|---|---|
| 1 | ninguna mano sale sin entrada de trazabilidad | registro de decisiones | fallaría | una edición manual sin motivo | `record_uid` | **no** | 0 salidas sin entrada |
| 2 | todo registro parsea y cumple esquema | parser independiente | **pasa** | corrupción de línea | — | no | 1258/1258 |
| 3 | ninguna acción de posición no declarada | comparación cruzada | **fallaría** (7) | acción huérfana | — | no | 0 huérfanas |
| 4 | ninguna posición en dos jugadores | recuento | **fallaría** (3) | doble asignación | — | no | 0 duplicadas |
| 5 | `amount` nunca se lee sin `amount_type` | campo ausente | **fallaría** (13826) |confusion de semántica | `amount_type` | no | 0 sin marca |
| 6 | histórico y operativa declaran su diferencia | manifiesto de exclusiones | **fallaría** | `75bbdb7` | `record_uid` | no | diferencia = conjunto declarado |
| 7 | cada exclusión tiene motivo vigente | motivo **en el código** | **fallaría** | `EXCLUSIONES_VENTANA_FABLE` | filtros | **sí, parcialmente** | ningún motivo declarado falso |
| 8 | cada métrica declara su población | `hands_input` del sello | **fallaría** (10 de 12 sin `meta`) | derivado sin población | sello | no | 12/12 con `meta` |
| 9 | ninguna cifra se publica sin ventana | campo `ventana` | **fallaría** | agregación mezclando semánticas | ventanas | no | toda cifra con ventana |
| 10 | el hash del histórico cambia si cambia la operativa | dos hashes | **pasa hoy** (no hay histórico) | edición no declarada | `record_uid` | no | hash distinto al cambiar |

**[C]** **Cuatro fallarían** (3, 4, 5, 9), **tres más** (1, 6, 8) y una es
**parcialmente tautológica** (la 7: comprueba el motivo contra el propio código
que lo declara).

**[D]** Las 10 se proponen **precisamente porque fallan**. **[D]** La 8 es la
que más valor tiene: obliga a que cualquier derivado declare su población, que
es el requisito que `observations.json` no cumple hoy.

**[P]** Prueba adicional, **[D]** no tautológica por construcción: **verificar
que una métrica calculada con dos poblaciones distintas da dos resultados
distintos**. Si dan igual, el filtro no está filtrando.

---

## 9. Secuencia de migración reversible

**[P]** Cada paso es reversible y ninguno toca datos antes de aprobar el
anterior.

| paso | acción | reversible | bloqueado por |
|---|---|---|---|
| **0** | **[P]** aprobar la v0 **como referencia**: registrar SHA, esquema, incertidumbres | se añade una nota | **decisión 1** |
| **1** | **[P]** crear `motor/identidad.py` con `record_uid` y `session_id`, **en modo sombra**: no cambia quién lee | sí, es aditivo | decisión 2 |
| **2** | **[P]** indexar la v0 por `record_uid` y publicar el manifiesto | sí | decisión 2 |
| **3** | **[P]** añadir las 22 al **histórico** con su estado, **sin tocar la operativa** | sí, es aditivo | **decisiones 3 y 4** |
| **4** | **[P]** escribir el primer filtro versionado, **sin aplicarlo** | sí | **decisión 5** |
| **5** | **[P]** hacer que `load_hands()` acepte un filtro, con **default = sin filtro** | sí: el default reproduce el comportamiento actual | decisión 5 |
| **6** | **[P]** aplicar el filtro a **un** análisis, y publicar los dos resultados | sí | decisión 6 |
| **7** | **[P]** reescribir los derivados con su `meta` completo | **difícil**: requiere regenerar | decisión 7 |
| **8** | **[P]** migrar los procesos que escriben | difícil | decisión 8 |

**[D]** **Los pasos 0 a 6 no invalidan ningún derivado.** El 7 sí, y es el único
peligroso. **[D]** Por eso la v0 **no cambia** en ningún paso: es el ancla.

**[D]** **Ningún paso de esta secuencia se ha ejecutado.**

---

## 10. Decisiones que requieren aprobación antes de implementar

| # | decisión | por qué bloquea | alternativa si no se decide |
|---|---|---|---|
| **1** | ¿se aprueba la v0 como referencia inmutable? | paso 0 | nada avanza |
| **2** | ¿se crea `motor/identidad.py`? | pasos 1-2 | se sigue sin identidad global |
| **3** | ¿entran las 22 al histórico? | paso 3 | siguen fuera de todo registro legible |
| **4** | ¿se declara `RETIRADA_PENDIENTE`? | paso 3 | la situación sigue sin nombre |
| **5** | ¿qué filtro se escribe primero? | pasos 4-5 | las poblaciones siguen implícitas |
| **6** | ¿a qué análisis se aplica primero? | paso 6 | sigue sin población declarada |
| **7** | ¿se regeneran los derivados? | paso 7 | 10 de 12 siguen sin población conocida |
| **8** | ¿se migran los procesos que escriben? | paso 8 | pueden seguir editando la operativa |
| **9** | ¿se recupera `H_1015`? | paso 3 | sigue fuera |
| **10** | ¿se acepta `event_uid = null` para las 1258? | paso 2 | se planifica una identidad que no se puede construir |

**[D]** La **10** es la más incómoda y la menos visible: **[C] el modelo de
identidad que esta fase propone **no puede asignar identidad de evento** a
ninguna mano existente, porque falta el identificador de fotograma. **[P]** La
solución no es inventar una identidad retrospectiva, sino **capturar manos
nuevas** con ese campo.

**[D]** **[P] La decisión 10 es la única cuya respuesta es «no se puede», y por
eso no puede esperar a las demás.**

---

## 11. Verificación

**[M]** Canónica: **1 782 206 bytes · 1258 líneas** · SHA
`35727961646dfaba2c67fd5ee0dbe9b0669d3156f9c6f3fa3585060a93f097e2` **✓**.

**[M]** Las ocho fuentes conservan sus hashes: `35727961646dfaba`,
`ec868e9305d1e03a`, `032bc79c0a18988c`, `202a1f548fc60bac`, `35727961646dfaba`,
`31eba6e1c4824015`, `e7fbae80fe60e019`, `9f1f61b53268df81`.

**[M]** `HEAD` **antes y después: `1dda6aa`**. Staged vacío. Sin cambios ajenos
tocados.

**[M]** No se modificó ninguna base, ni grabador, ni motor, ni pruebas. No se
recuperó, eliminó ni fusionó ningún registro. **No se ejecutó la migración.**

**[M]** Modificado únicamente: `AUDITORIA_SEMANTICA_GRABADOR.md`.

**[M] Ningún commit.**

### 11.1 Limitaciones de esta fase

**[D]** No se comprobó **qué código generó cada uno de los 10 derivados sin
`meta`**. Se declara **no reproducible**, no «obsoleto»: **[D]** sin su
población conocida no se puede afirmar que estén mal, solo que no se pueden
verificar.

**[D]** El conteo de consumidores (**66 ficheros**, **16 procesos**) es por
mención de texto, no por análisis estático del flujo de datos. **[P]** Falta un
`auditar_consumidores.py` que siga las llamadas de verdad; el fichero ya existe
en `tools/` y **[D]** podría no cubrir este caso.

**[D]** La secuencia del § 9 está ordenada por dependencia, **no por
importancia**. **[D]** Los pasos 0 a 6 son de bajo riesgo y bajo coste; el 7 es
el caro y el que puede invalidar trabajo existente.

---
---

# PARTE IX — REVISIÓN LITERAL DE LAS DIEZ DECISIONES

Fase de diseño. **No se modificó código ni datos. No hubo commit.** No es otra
auditoría general: es la conversión del diseño de la Parte VIII en decisiones
verificables.

## 0. Verificación de las condiciones de aprobación de la v0

**[C]** Las siete condiciones propuestas, comprobadas una a una:

| condición | resultado |
|---|---|
| el fichero original no se modifica ni reescribe | **[C]** `git diff --quiet` limpio; mtime sin alterar |
| se conserva el SHA-256 completo | **[C]** `35727961646dfaba2c67fd5ee0dbe9b0669d3156f9c6f3fa3585060a93f097e2` ✓ |
| se conserva el tamaño exacto | **[C]** 1 782 206 bytes |
| se conserva el número de registros | **[C]** 1258, con 0 líneas ilegibles |
| ids distintos | **[C]** 1258 (dentro de este fichero) |
| esquema documentado | **[C]** mano: 11 claves; acción: 4 claves |
| commit que la dejó así | **[C]** `33ab8ee6b1107a71ee1702bdab37823b3e5ca2b2`, 2026-10-16 18:53:36 |

**[C] Las siete condiciones se cumplen hoy.** **[D]** Aprobar la v0 **no**
certifica que las 1258 manos se capturaran bien: acepta que **esos** son los
datos de referencia, con las limitaciones del § 1.3 de la Parte VIII.

---

## 1. Cuatro correcciones que esta revisión obliga a la Parte VIII

**[C]** Los hallazgos planteados son correctos y cambian el diseño. Se corrige
aquí, no se reescribe la Parte VIII.

### 1.1 El sello presenta una reproducibilidad aparente

**[C]** `motor/_procedencia.py` registra `arbol_sucio`, pero **no emite un
veredicto**. Con `code_commit: 8e527c3` y `arbol_sucio: True`, un lector ve un
commit identificable y puede concluir que el derivado es reproducible. No lo es:
falta el código efectivo.

**[D] Corrección:** el sello debe llevar un campo explícito.

```json
"reproducible": false,
"motivo_irreproducible": ["arbol_sucio:True"],
"entradas": {...}, "parametros": {...}, "procedimiento": "..."
```

**[D]** La regla: **`reproducible: false` si falta cualquiera de los cinco
elementos** —código efectivo, entradas, parámetros, procedimiento y población.
**[D]** Un sello sin veredicto es peor que ningún sello, porque aparenta lo que
no sabe.

### 1.2 `record_uid` no resuelve el doble conteo analítico

**[C]** La Parte VIII afirmó que indexar por `record_uid` —que incluye el hash
del fichero— evitaba el doble conteo. **Se afirmaciones con demasiada fuerza**: eso impide que dos
registros **se confundan como el mismo**, y no impide que **se cuenten dos
veces**.

**[C]** El caso real: `hands_db_old.jsonl` comparte **268 contenidos** con la
canónica. Con `record_uid` distinto para cada uno, ambos entran en el histórico
—correcto— y ambos podrían entrar en una misma población.

**[D] Corrección:** el filtro debe producir, además de la población, un
**informe de coincidencias**:

```json
"coincidencias": [
  {"content_fp": "…", "records": ["uid:A", "uid:B"],
   "relacion": "MISMO_CONTENIDO_DISTINTA_FUENTE",
   "certeza": "INDETERMINADA",
   "cuenta_una_vez": false}
]
```

**[D]** La pregunta que el filtro debe responder explícitamente es: **«¿cuento
estas dos como una mano o como dos?»** **[P]** Por defecto, **dos**, con la
advertencia a la vista. Fusionar sin evidencia de identidad de evento es
exactamente el error que esta auditoría ha documentado.

### 1.3 La identidad del registro no depende de la identidad del evento

**[D]** Confirmado y ya implementado en § 3.1: `record_uid` se construye
siempre; `event_uid` es `null` mientras no haya evidencia. **[D]** Por tanto
**la migración histórica no está bloqueada** por la ausencia de `event_uid`: los
pasos 0 a 6 del § 9 no dependen de él.

### 1.4 Conservar la firma no conserva el comportamiento

**[C]** La función es **`learn.load_hands()`** —no `load_hints()`— y tiene
**[C] 60 puntos de llamada**. **[D]** Un filtro por defecto «sin restricción»
debería reproducir el comportamiento, pero **eso hay que demostrarlo**, no
suponerlo.

**[P]** Regresión obligatoria antes de tocar el lector, con **captura del
estado anterior**:

| # | qué se compara | por qué |
|---|---|---|
| R1 | **número de registros** y **orden** de salida | un cambio de orden altera `preflop_events()` y con él las categorías |
| R2 | **valor de cada campo** de cada mano | el lector no puede transformar nada «sin querer» |
| R3 | **casos de duplicación** | hay 1 contenido duplicado conocido; debe comportarse igual |
| R4 | **fichero ausente** | hoy devuelve vacío o lanza; hay que fijar cuál |
| R5 | **fichero malformado** | hoy hay 1 línea ilegible en otro fichero; el comportamiento debe fijarse |
| R6 | **`reliable_only=True`** | **[C]** excluye 23 ids de `EXCLUSIONES_VENTANA_FABLE`; su efecto debe ser idéntico |
| R7 | **`max_hands`** | **[C]** corta por número de líneas; ¿por líneas o por registros válidos? hoy son lo mismo, **no deben dejarlo de serlo** |

**[D]** La regresión se ejecuta **contra el lector actual**, no contra una
referencia escrita a mano: si no, no sería independiente.

---

## 2. Las diez decisiones, literalmente

**[C]** Texto literal de § 10, con la evidencia, la consecuencia y las
dependencias que faltaban.

| # | decisión (literal) | evidencia que la sostiene | consecuencia de aprobarla | depende de |
|---|---|---|---|---|
| **1** | «¿se aprueba la v0 como referencia inmutable?» | **[C]** las 7 condiciones verificadas (§ 0) | el resto del diseño tiene ancla | — |
| **2** | «¿se crea `motor/identidad.py`?» | **[C]** `record_uid` es construible hoy; **[C]** 60 llamadas se pueden redirigir | existe identidad de registro | 1 |
| **3** | «¿entran las 22 al histórico?» | **[C]** están en `02fc641`; **[C]** ninguna tiene contenido en la v0; **[C]** el criterio sigue sin establecerse | dejan de estar fuera de todo registro legible | 1 |
| **4** | «¿se declara `RETIRADA_PENDIENTE`?» | **[C]** 21 de 22 tienen lista sin razonamiento; 1 no tiene lista | la ambigüedad tiene nombre y no se hereda como si fuera fundamento | 3 |
| **5** | «¿qué filtro se escribe primero?» | **[C]** hoy 10 de 12 derivados no declaran población | las poblaciones dejan de ser implícitas | 1, 2 |
| **6** | «¿a qué análisis se aplica primero?» | **[C]** hay 2558 calls medidas por ventana; es el candidato natural | un análisis tiene población declarada | 5 |
| **7** | «¿se regeneran los derivados?» | **[C]** 0 de 12 reproducibles con evidencia suficiente | 12 derivados con población declarada — **si el sello se corrige (§ 1.1)** | 6, y **R1–R7** |
| **8** | «¿se migran los procesos que escriben?» | **[C]** 16 procesos escriben o respaldan | dejan de poder editar la operativa en silencio | 1, 2, 5 |
| **9** | «¿se recupera `H_1015`?» | **[C]** no figura en ninguna lista; **[C]** sin contradicciones internas; **[C]** semántica W4 delimitada | una mano vuelve a la operativa | 3, **y el criterio de `75bbdb7`** |
| **10** | «¿se acepta `event_uid = null` para las 1258?» | **[C]** no hay identificador de fotograma en el esquema | la incertidumbre se representa en vez de inventarse | 1 |

**[P] Decisión 11, que falta en § 10 y es la que resuelve la 10:**
«¿se instrumenta la captura futura con identificador de fotograma y
`amount_type`?» **[C]** El código actual **ya** escribe `amount_type` desde
`8bd55be`. **[C]** Ninguna mano de la base lo tiene. **[D]** Sin la 11, la 10
es una aceptación permanente y no un estado transitorio.

---

## 3. Clasificación en los cuatro grupos

### 3.1 Aprobables ahora

| # | condición de aprobación |
|---|---|
| **1** | las 7 condiciones, verificadas. **[D]** Ninguna depende de nada pendiente |
| **2** | **en modo sombra**: se crea el módulo y se indexa, **sin cambiar quién lee**. **[D]** Es aditivo y reversible |
| **4** | es una convención de nombres. **[D]** No toca datos |
| **10** | **[C]** es la única respuesta honesta. **[D]** Sin identidad de evento no hay nada que decidir |

### 3.2 Requieren prueba adicional

| # | prueba que falta |
|---|---|
| **5** | **[D]** los filtros deben admitir el informe de coincidencias (§ 1.2). **[P]** Sin eso, el filtro puede duplicar manos sin avisar |
| **6** | **[P]** aplicar un filtro exige **R1–R7** comparando contra el lector actual, no contra una referencia manual |
| **7** | **[P]** exige la corrección del sello (§ 1.1). **[D]** Regenerar con el sello actual produciría derivados con reproducibilidad aparente |
| **9** | **[D]** exige el criterio de `75bbdb7`, que no se tiene. **[C]** Sin él, recuperar es una apuesta, no una reparación |

### 3.3 Deben permanecer pendientes

| # | por qué |
|---|---|
| **8** | **[D]** depende de que el filtro tenga informe de coincidencias y de que los consumidores cambien de lector. **[P]** Adelantarla deja procesos escribiendo en dos sitios |

### 3.4 Depende de instrumentar la captura futura

| # | vínculo |
|---|---|
| **11** | es la **precondición** para que `event_uid` deje de ser `null` algún día |
| **10** | **[D]** mientras la 11 no exista, la 10 es permanente. **[D]** Ninguna decisión de esta lista puede resolverlo |

**[C]** Gráfico de dependencias:

```
  1 (v0)
  ├── 2 (identidad, sombra) ──┬── 5 (filtro) ── 6 (análisis) ── 7 (derivados)
  │                           └── 8 (escritores)
  ├── 3 (las 22) ── 4 (estado)
  └── 10 (event_uid = null)      11 (instrumentar)  ← independiente
       ▲                                              ▲
       └────────────── identidad de evento, algún día ─┘
```

---

## 4. Lo que esta revisión NO propone

**[D]** No se propone aprobar los ocho pasos en bloque. **[D]** No se propone
regenerar derivados. **[D]** No se propone tocar `load_hands()`.

**[P]** El orden que se deduce de la clasificación:

| orden | decisiones | carácter |
|---|---|---|
| 1.ª | **1** | ancla; no cambia nada |
| 2.ª | **2** (sombra) · **4** · **10** | aditivas, reversibles |
| 3.ª | **3** | mueve datos al histórico; requiere la 1 |
| 4.ª | **11** | afecta solo a capturas futuras |
| 5.ª | **5** → **6** | requieren las regresiones R1–R7 |
| 6.ª | **8** | requiere filtros con informe de coincidencias |
| 7.ª | **7** | la más cara; **no aprobar aún** |

---

## 5. Verificación

**[M]** Canónica: **1 782 206 bytes · 1258 líneas** · SHA
`35727961646dfaba2c67fd5ee0dbe9b0669d3156f9c6f3fa3585060a93f097e2` **✓**.
Las ocho fuentes conservan sus hashes.

**[M]** `HEAD` = `1dda6aa`, sin cambios. Staged vacío. Ningún cambio ajeno
tocado.

**[M]** No se modificó ninguna base, ni grabador, ni motor, ni pruebas. No se
ejecutó migración, ni recuperación, ni regeneración.

**[M]** Modificado únicamente: `AUDITORIA_SEMANTICA_GRABADOR.md`.
**Ningún commit.**

### 5.1 Nota factual

**[C]** La función de lectura es **`learn.load_hands()`**. No existe
`load_hints()`. **[C]** Tiene **60 puntos de llamada**, cifra que la Parte VIII
no recogía y que sitúa el coste de la decisión 6 por encima de lo allí escrito.