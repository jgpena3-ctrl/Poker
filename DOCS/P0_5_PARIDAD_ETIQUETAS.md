# P0-5 — Paridad y fiabilidad de etiquetas de jugadores (sombra)

Estado: **auditoría cerrada y detenida para revisión**. El contrato es
`shadow-only`: no cambia etiquetas efectivas, modelos, rangos, priors,
probabilidades ni recomendaciones. No se activa P0-1, P0-2, P0-3 ni P0-4.

Base auditada: `data/hands_db.jsonl`, ventana fiable de **877 manos**,
hash `ea99bae67b61e213200b2ad2c0e0706121e7a7e7ef2a065941702a014f36e8ed`.
Procedencia de la base: **`partial`** (P0-4; B1 no demostró la reproducción).
Etiquetas efectivas de entrenamiento: **138 jugadores**, 78 PEZ / 60 TIBURON,
sha256 `dca28d2607e817b8794b4579602bbe8cedf456754377d17dfa5b9e39cb8e6060`.

La conclusión corta: **las dos implementaciones no calculan la misma
clasificación**, aunque ambas usen los nombres `PEZ` y `TIBURON`. La regla de
stack coincide exactamente cuando se les da la misma evidencia; la diferencia
está en que serving no dispone de VPIP/PFR y no consulta la etiqueta histórica.

---

## 1. Alcance y no cambios

Se auditaron, sin modificarlos:

- `Profiles.simple_label` y `PlayerProfile._simple_label`;
- la construcción de perfiles en `Profiles.from_hands` y `build_models`;
- las estadísticas que alimentan las etiquetas (`TransitionStats`);
- `Asistente._perfil_for` y sus dos consumidores live;
- los consumidores de entrenamiento (`ProfileRangeModel`, `Oracle`,
  `PostflopRangeModel`, `behavior_table`);
- el artefacto histórico `data/profiles.json`.

No se tocaron datos canónicos, derivados, hashes, manifiestos, pins, la ventana
de 877, matrices preflop, rangos, priors, probabilidades, selección de
observaciones, etiquetas efectivas, recomendaciones live ni
`MULTIWAY_SOPORTADO=False`. No se inició B2, ni calibración, ni sesión real.

---

## 2. Auditoría de las implementaciones actuales

### 2.1 Entrenamiento

Cadena exacta:

```
data/hands_db.jsonl
  -> learn.load_hands(reliable_only=True)          # 877 manos
  -> stats.TransitionStats.from_hands(hands)
  -> profile.Profiles.from_hands(hands)
  -> profile.PlayerProfile._simple_label()
  -> profile.simple_label(vpip, pfr, stack_mean)
  -> build_models(): labels = {nombre: p.label}
```

`TransitionStats` recorre `players[].pos`, `players[].name` y
`learn.preflop_events(hand)`. Solo los eventos preflop con jugador identificado
crean contadores. Para cada evento:

- `vpip.opp += 1` y `pfr.opp += 1`;
- `vpip.act += 1` si la categoría está en `MONEY_CATS`;
- `pfr.act += 1` si la categoría está en `RAISE_CATS`.

`PlayerProfile.n` es **el denominador de VPIP**, no el número total de manos del
jugador. `PlayerProfile.counts[stat]` guarda `(opp, act)`; `stats[stat]` guarda
`act / opp` o queda ausente si `opp == 0`.

`mean_stack_by_player` recorre `players[].stack` de todas las manos de la
ventana. Descarta `None` y valores no numéricos; conserva el `0.0` real; no
deduplica por sesión. La media es la del dataset, en BB.

Regla de `simple_label`, en este orden estricto:

| Prioridad | Condición | Etiqueta | Variables |
|---|---|---|---|
| 1 | `stack_mean is not None and stack_mean < 50.0` | `PEZ` | stack medio del dataset (BB) |
| 2 | si no, `vpip > 0.32 and pfr < 0.10` | `PEZ` | tasas `act/opp` |
| 3 | resto | `TIBURON` | incluye desconocidos y ausencia de datos |

Notas exactas:

- Los umbrales son estrictos: `49.99` es PEZ; `50.0` no. `vpip=0.32` no dispara
  el fallback; `pfr=0.10` tampoco.
- El stack tiene precedencia sobre las estadísticas. Un jugador con stack medio
  bajo es PEZ aunque su VPIP/PFR digan lo contrario.
- Si falta VPIP o PFR, `_simple_label` llama a `simple_label(None, None, stack)`;
  aplica solo la regla de stack y, si no, devuelve `TIBURON` conservador.
- Si faltan stack, VPIP y PFR, devuelve `TIBURON`. Ese `TIBURON` es el valor por
  defecto del clasificador, **no una clasificación validada**. El contrato P0-5
  lo marca como `insufficient_evidence` y su `contract_label` queda `UNKNOWN`;
  no convierte la ausencia en TIBURON.
- Solo VPIP, PFR y stack alimentan la etiqueta. `b3`, `cbet`, `wtsd`, `wsd`,
  `bar`, `rb`, etc. se calculan y se guardan en el perfil, pero no participan en
  `simple_label`.
- `PlayerProfile.reliability()` usa `HANDS_BANDS = ((40,'probable'),
  (500,'confiable'), (5000,'individual'))`. Con `n=1` o `n=2` devuelve
  `'probable'`, que es el **primer tramo**, no una probabilidad de acierto.
- `confidence` es la masa media de los bins modales de una posterior Beta por
  estadística; no es una calibración de la etiqueta.

### 2.2 Serving

Cadena exacta:

```
estado live
  -> Asistente._observe_stacks(): guarda un stack por cambio visible y activo
  -> Asistente._perfil_for(player_id, state)
  -> media de live_stacks, o stack actual, o TIBURON
```

`_perfil_for` implementa:

| Prioridad | Condición | Etiqueta | Evidencia |
|---|---|---|---|
| 1 | hay historial de sesión y `mean(live_stacks) < 50.0` | `PEZ` | media de stacks visibles |
| 2 | si no hay historial y `state[pid_stake] < 50.0` | `PEZ` | stack actual |
| 3 | sin media y sin stack | `TIBURON` | ninguna |

Notas exactas:

- `_observe_stacks` solo añade un valor cuando el stack cambia respecto de
  `_last_seen_stake` y el jugador está `activo`; la media es de **cambios
  visibles**, no de todas las manos históricas.
- Serving **no usa VPIP, PFR, `n`, nombre del jugador ni `models.labels`**.
- `models.labels` se construye y se guarda, pero `_perfil_for` no lo consulta.
  `_villain_name` se usa para mostrar el nombre, no para elegir etiqueta.
- Sin stack, el `TIBURON` es un fallback conservador, no una clasificación con
  evidencia. El contrato lo marca `insufficient_evidence` y su
  `contract_label` queda `UNKNOWN`.
- La comparación de nombres `PEZ`/`TIBURON` entre entrenamiento y serving **no
  implica la misma clasificación**: una usa stack medio + VPIP/PFR; la otra usa
  solo stacks de sesión.

### 2.3 Consumidores

Entrenamiento (`build_models`):

- `labels` se pasa a `ProfileRangeModel.from_hands`, `Oracle(build(...))` y
  `PostflopRangeModel.from_hands`.
- `ProfileRangeModel` usa `labels.get(ev.player)`: si falta la etiqueta, **salta
  la observación**; no la atribuye a TIBURON.
- `PostflopRangeModel` hace lo mismo: `labels.get(o.player)` y, si falta, salta
  la observación.
- `behavior_table` usa `by_player.get(o.player, '?')`: un consumidor externo con
  un mapa incompleto crearía una etiqueta `'?'`, no TIBURON. En `build_models`
  el mapa es completo, así que este caso no se usa en producción.
- `Oracle.p_action(label, ...)` busca primero la celda del perfil; si no existe,
  cae a `label`, luego a `poblacion`. Un cambio de etiqueta en serving cambia
  **qué tabla de perfil se consulta**.

Serving live:

- `asistente_live.py:1186` (`_equity_main`/rango) y `:1562`
  (`_recomendacion_para`) llaman a `_perfil_for`.
- El resultado se usa para `range_model.prob_vec(perfil, ...)`,
  `postflop_model.p_action(perfil, ...)` y las tablas de `Oracle`.
- Por tanto, la discrepancia no es solo cosmética: un jugador que contribuyó a
  la tabla PEZ puede ser consultado como TIBURON en serving, y el modelo le
  devolverá la tabla agregada TIBURON en lugar de la suya.
- `db_health.py` también construye `labels` y salta jugadores sin etiqueta, pero
  es diagnóstico, no serving.

---

## 3. Contrato contextual de etiquetas

Implementado en `motor/label_contract.py`. Es de solo lectura y no está
conectado a ninguna decisión live.

### 3.1 Campos registrados

Cada `LabelDecision` registra:

- `label`: etiqueta efectiva producida por el clasificador;
- `contract_label`: etiqueta que el contrato acepta como clasificación
  (`UNKNOWN` si el estado es insuficiente, desconocido o incompatible);
- `method`: regla aplicada (`stack_mean_lt_50bb`,
  `loose_passive_fallback`, `default_rest`, `default_no_evidence`,
  `session_mean_lt_50bb`, `current_stack_lt_50bb`,
  `default_tiburon_no_info`, `historical_artifact_label`);
- `variables`: valores exactos usados (stack, VPIP, PFR, umbrales, conteos);
- `hands_n`: manos de la ventana, cuando se conoce;
- `relevant_observations`: `(opp, act)` de VPIP/PFR, observaciones de stack;
- `provenance` y `provenance_status`: fuente y estado P0-4;
- `window`, `window_hash`, `built_commit`: ventana y commit cuando existen;
- `uncertainty`: motivos concretos de incertidumbre;
- `rules_blocking`: reglas que impidieron asignar una etiqueta validada;
- `reproducible`: si la regla se puede repetir con los campos dados;
- `valid_for_serving`: **diagnóstico de sombra**, nunca leído por serving.

No se rellena ningún campo ausente. Un `None` del artefacto sigue siendo `None`.
No se infiere commit, fecha, ventana ni hash que el artefacto no registre.

### 3.2 Estados

| Estado | Significado |
|---|---|
| `historical` | etiqueta leída de un artefacto histórico; no es cálculo actual |
| `current_evidence` | etiqueta calculada con evidencia actual y todos los inputs de la regla |
| `provisional` | inputs presentes, pero `n` por debajo del primer tramo ya declarado (`40`); diagnóstico, no mínimo nuevo |
| `unknown` | no hay etiqueta o no hay información para clasificar |
| `insufficient_evidence` | falta una variable requerida por la regla aplicada; el valor por defecto no se valida |
| `incompatible_provenance` | la evidencia no es conciliable con la base actual (hash incompatible o entrada sin contraparte) |

El estado `provisional` **no introduce un umbral nuevo**: reutiliza
`HANDS_BANDS[0][0] == 40`, que ya existe en `profile.py`, y solo lo usa para
marcar el primer tramo. No cambia ninguna etiqueta ni bloquea nada.

### 3.3 Resultados de comparación

| Resultado | Significado |
|---|---|
| `coincident` | entrenamiento y serving producen la misma etiqueta |
| `different` | etiquetas distintas con la misma regla de stack pero evidencia de stack distinta (media del dataset vs stack de sesión) |
| `historical_not_reproducible` | la etiqueta histórica no se puede reproducir con la evidencia actual |
| `insufficient_evidence` | faltan variables requeridas |
| `serving_data_unavailable` | serving no dispone de la evidencia que decidió la etiqueta de entrenamiento (VPIP/PFR) |
| `incompatible_provenance` | la procedencia no es conciliable |
| `unknown` | no hay etiqueta que comparar |

Una etiqueta determinista no se considera válida por sí sola: `reproducible=True`
solo dice que la regla se repite; la validez exige además evidencia suficiente y
procedencia adecuada. Por eso `valid_for_serving` es `False` para históricos,
desconocidos e insuficientes.

---

## 4. Muestras pequeñas señaladas

Los cuatro jugadores tienen etiqueta histórica y actual **PEZ**, pero no por la
misma razón ni con la misma reproducibilidad en serving.

| Jugador | n VPIP | stacks (BB) | media | último | regla | estado | serving media | serving actual | histórico |
|---|---:|---|---:|---:|---|---|---|---|---|
| `Valentina22` | 2 | `[53.3, 44.3]` | 48.8 | 44.3 | stack `<50` | `provisional` | `coincident` | `coincident` | PEZ, reproducible desde campos |
| `Sp1609` | 1 | `[123.5]` | 123.5 | 123.5 | fallback VPIP/PFR | `provisional` | `serving_data_unavailable` | `serving_data_unavailable` | PEZ, reproducible desde campos |
| `Ocampo99` | 2 | `[100.0, 99.0]` | 99.5 | 99.0 | fallback VPIP/PFR | `provisional` | `serving_data_unavailable` | `serving_data_unavailable` | PEZ, reproducible desde campos |
| `Nnn1` | 2 | `[100.0, 100.0]` | 100.0 | 100.0 | fallback VPIP/PFR | `provisional` | `serving_data_unavailable` | `serving_data_unavailable` | PEZ, reproducible desde campos |

Lectura individual:

- **`Valentina22`**: PEZ por stack medio `48.8 < 50.0`. La evidencia de stack es
  frágil: dos observaciones, una por encima del umbral (`53.3`) y otra por
  debajo (`44.3`); el margen de la media es **1.2 BB**. Serving con media y con
  último stack también da PEZ. La etiqueta es reproducible, pero no se declara
  estadísticamente suficiente.
- **`Sp1609`**: stack medio `123.5`, muy por encima de 50. Su PEZ sale **solo**
  del fallback `VPIP=1.0`, `PFR=0.0`, con `n=1`. Serving, que solo ve stack, da
  TIBURON. No es un error de implementación: es una diferencia por evidencia no
  disponible en serving.
- **`Ocampo99`**: mismo patrón que `Sp1609`, con `n=2`, `VPIP=1.0`, `PFR=0.0`,
  stack `99.5`. Serving da TIBURON.
- **`Nnn1`**: mismo patrón, con `n=2`, `VPIP=0.5`, `PFR=0.0`, stack `100.0`.
  Serving da TIBURON.

Sobre la suficiencia: los cuatro tienen las variables que exige la regla que se
aplicó, pero `n=1` o `n=2`. No se declara evidencia suficiente; se declara
`provisional` por el primer tramo ya existente de `HANDS_BANDS`. No se propone
un mínimo nuevo ni se convierte la ausencia en PEZ/TIBURON. La `reliability()`
actual devuelve `'probable'` para los cuatro porque es el tramo más bajo
(`n < 40`); eso **no** significa que la etiqueta sea probablemente correcta.

---

## 5. Comparación entrenamiento vs serving

Se ejecutaron ambos clasificadores sobre los mismos 138 jugadores. Para serving
se usan dos simulaciones reproducibles, porque no se abrió una sesión real:

1. **media de sesión**: se le pasa a `_perfil_for` la lista de stacks observados
   en la ventana (misma evidencia de stack que la media de entrenamiento);
2. **stack actual**: se le pasa el último stack observado, sin historial de
   sesión (rama de stack actual).

Ambas llaman al método real `Asistente._perfil_for`; no a una copia.

### 5.1 Conteos globales

| Comparación | `coincident` | `different` | `serving_data_unavailable` | `insufficient` | `incompatible` | `unknown` |
|---|---:|---:|---:|---:|---:|---:|
| entrenamiento vs serving (media de sesión) | 116 | 0 | 22 | 0 | 0 | 0 |
| entrenamiento vs serving (stack actual) | 98 | 22 | 18 | 0 | 0 | 0 |

Control de implementación de la regla de stack, con **la misma evidencia**:

- media: 138/138 coinciden, 0 errores;
- stack actual: 138/138 coinciden, 0 errores.

Es decir: **no hay errores de implementación en la regla de stack**. Las 40
diferencias con stack actual se explican por dos causas declaradas:

- 18 por `serving_data_unavailable`: entrenamiento decidió por VPIP/PFR y
  serving no tiene esa evidencia;
- 22 por `different`: misma regla de stack, pero la media del dataset y el
  último stack de la ventana no son el mismo valor.

Con media de sesión, las 22 diferencias son todas `serving_data_unavailable`.
No hay ninguna diferencia no explicada.

### 5.2 Dirección de las diferencias

| Comparación | PEZ -> TIBURON | TIBURON -> PEZ |
|---|---:|---:|
| media de sesión | 22 | 0 |
| stack actual | 33 | 7 |

- Con media, el serving **subetiqueta PEZ**: 22 jugadores que el entrenamiento
  llama PEZ (por fallback) pasan a TIBURON.
- Con stack actual, además de las 18 por fallback, hay 15 PEZ->TIBURON y 7
  TIBURON->PEZ por cambio de stack entre la media del dataset y el último stack.
  Es una diferencia de ventana de evidencia, no de implementación.

Ejemplos reproducibles:

- `mur420`: entrenamiento PEZ (`n=131`, stack medio 57.6; fallback), serving
  media/actual TIBURON. `serving_data_unavailable`.
- `Sp1609`, `Ocampo99`, `Nnn1`: mismo patrón.
- `Arquejandro`: entrenamiento TIBURON (stack medio 103.1), serving con último
  stack 39.8 -> PEZ. `different` por ventana de evidencia.
- `Hellfish1`: entrenamiento PEZ (stack medio 41.1), serving con último stack
  51.7 -> TIBURON. `different` por ventana de evidencia.

La lista completa está en `differences_session_mean` y
`differences_current_stack` de `python tools/auditar_etiquetas.py --json`.

### 5.3 Etiquetas históricas

`data/profiles.json` contiene 139 entradas y coincide con el hash canónico
declarado por `calibration_window.json`, pero P0-4 lo clasifica como
`historical derivative` con procedencia **`partial`**, no verificado.

| Hecho | Valor |
|---|---:|
| entradas históricas | 139 |
| jugadores comunes con la ventana actual | 138 |
| etiquetas coincidentes | 138 |
| etiquetas diferentes | 0 |
| solo históricos | 1 (`HERO`) |
| solo actuales | 0 |
| `n` distinto | 12 jugadores |
| estadísticas distintas | 24 jugadores |
| stack medio distinto | 1 jugador (`Jeffer30bog`: 19.83 vs 20.0) |

La coincidencia de etiquetas es real, pero **no convierte el artefacto en una
reproducción verificada**. Los contadores y estadísticas no son idénticos:
por ejemplo, `Arquejandro` tiene `n=18` frente a `19`, y `Jarduan` `n=864` frente
a `866`; varias estadísticas difieren (`cbet`, `bar`, `rb`, `vpip`, `pfr`,
`wtsd`), y algunas ausencias actuales aparecen como `0.0` en el artefacto
(`rb`/`bar`). El artefacto no registra commit, fecha, ventana ni hash de base,
así que **no se infiere la causa**. La etiqueta puede coincidir aunque la
evidencia no sea la misma.

`HERO` es una entrada histórica sin contraparte en la ventana actual: `n=1`,
`stack_mean=67.6`, `VPIP=0.0`, `PFR=0.0`, etiqueta `TIBURON`. No aparece en los
138 perfiles actuales. Se clasifica como `historical_not_reproducible` y
`incompatible_provenance`; no se rellena ni se le asigna una etiqueta actual.
No se investiga su origen en P0-5.

### 5.4 Resumen por categoría exigida

| Categoría | Conteo | Nota |
|---|---:|---|
| etiqueta coincidente | 116 (media) / 98 (stack actual) | 138 jugadores actuales |
| etiqueta diferente | 0 (media) / 22 (stack actual) | las 22 son diferencia de ventana de stack, no de implementación |
| etiqueta histórica no reproducible | 1 | `HERO`; 0 entre los 138 jugadores comunes |
| evidencia insuficiente | 0 actuales | 105 quedan `provisional`, no insuficientes; el contrato cubre ambos |
| datos no disponibles en serving | 22 (media) / 18 (stack actual) | falta historial VPIP/PFR, no falta stack |
| procedencia incompatible | 1 | `HERO`; el artefacto común es `partial`, no incompatible |
| clasificación desconocida | 0 actuales | el contrato la soporta y la prueba con casos sintéticos |

---

## 6. Integración con P0-1, P0-2, P0-3 y P0-4

- **P0-1** (contrato preflop estricto/legacy) no se activa ni se consulta para
  cambiar etiquetas.
- **P0-2** (elegibilidad) no filtra observaciones ni cambia etiquetas; no se usa
  en este bloque.
- **P0-3** (evidencia postflop) no se usa para validar etiquetas.
- **P0-4** se usa solo como fuente de procedencia: ventana de 877, hash de
  ventana, estado `partial` de `build_models`, estado `partial` y hash canónico
  de `profiles.json`. No se usa su matriz de compatibilidad para bloquear nada.

El contrato P0-5 no activa restricciones, no bloquea consultas live y no cambia
la etiqueta que serving sigue usando. `valid_for_serving` es un campo de
diagnóstico; ningún camino de producción lo lee.

---

## 7. Pruebas y evidencia de no cambio

### 7.1 Pruebas específicas

```
python -m pytest motor/test_label_contract.py -q
23 passed
```

Cubren:

- precedencia y umbrales estrictos de `simple_label`;
- regla de stack, fallback y estados `provisional`/`insufficient`;
- serving con media, stack actual y sin información;
- paridad de la regla de stack con la misma evidencia;
- histórico sin campos inventados, etiqueta ausente -> `UNKNOWN`;
- procedencia incompatible y comparaciones `unknown`,
  `historical_not_reproducible`, `insufficient` e `incompatible`;
- conteos globales y los cuatro jugadores;
- diferencias de evidencia histórica sin declarar identidad;
- no cambio de modelos, etiquetas ni vectores;
- no escritura sobre datos canónicos.

### 7.2 Suites adyacentes

```
python -m pytest motor/test_label_contract.py motor/test_profile.py \
  motor/test_player_ranges.py motor/test_postflop_ranges.py \
  motor/test_behavior.py motor/test_asistente_live.py \
  motor/test_provenance_contract.py motor/test_field_eligibility.py \
  motor/test_postflop_evidence.py motor/test_preflop_contract.py -q
254 passed, 1 xfailed
```

Las dos advertencias de `_prior_grid` (`FLAT_PRIOR=0.15`) son preexistentes y no
provienen de P0-5.

### 7.3 Suite completa: límite declarado

`python -m pytest motor -q` da **1036 passed, 1 skipped, 6 xfailed, 23 failed**.
Los 23 fallos son preexistentes y no pertenecen a P0-5: fijan cifras de la base
normalizada de 1253/1182 manos (`test_accion_p`, `test_auditar_origen`,
`test_cm004`, `test_diagnostico_grabador`, `test_lista_saneamiento`,
`test_quien_escribe`) mientras la base actual tiene 1344/1273. No se corrigen en
este bloque, no se ocultan y **no se declara la suite completa en verde**.

### 7.4 No cambio efectivo

- `labels_sha256` de las etiquetas efectivas:
  `dca28d2607e817b8794b4579602bbe8cedf456754377d17dfa5b9e39cb8e6060`.
- `test_audit_does_not_change_models_labels_or_vectors` construye
  `build_models(verbose=False)`, guarda etiquetas, digest de
  `postflop_model.to_json()` y un `prob_vec` concreto, ejecuta la auditoría y
  exige que los tres sean idénticos.
- `test_audit_is_read_only_on_canonical_data` verifica que
  `hands_db.jsonl`, `profiles.json`, `calibration_window.json` y
  `preflop_matrices.json` conservan su sha256.

---

## 8. Limitaciones declaradas

1. **Serving simulado, no sesión real.** La media de sesión se simula con los
   stacks de la ventana; `_observe_stacks` real deduplica cambios y solo ve
   estados visibles. Las conclusiones de paridad de sesión requieren una sesión
   real, que no se ejecutó.
2. **El artefacto histórico no es reproducible byte a byte.** Las etiquetas
   coinciden en los 138 jugadores comunes, pero 12 valores de `n`, 24 jugadores
   con alguna estadística distinta y 1 stack medio difieren. No se declara
   `verified`.
3. **`HERO` no tiene contraparte actual.** Se documenta como incompatible; no se
   rellena ni se investiga su origen.
4. **`reliability='probable'` no es confianza.** Para `n=1/2` es simplemente el
   primer tramo; `confidence` es masa Beta, no calibración.
5. **No se corrige serving.** La discrepancia queda auditada, no arreglada. Un
   cambio de serving para usar `models.labels` o VPIP/PFR requeriría otra
   autorización y validación.
6. **`behavior_table` con mapas incompletos** etiqueta `'?'`; en `build_models`
   el mapa es completo, así que no se observó en esta ventana.
7. **Sin umbral mínimo nuevo.** `provisional` solo reutiliza el tramo 40 ya
   declarado; no se propone ni se valida un mínimo estadístico.

---

## 9. Reproducción

```
python tools/auditar_etiquetas.py
python tools/auditar_etiquetas.py --json
python -m pytest motor/test_label_contract.py -q
```

El tool es de solo lectura. No construye `build_models`, no escribe artefactos,
no bloquea consultas y no activa ningún contrato.

---

## 10. Entregables

| Entregable | Ubicación |
|---|---|
| Documento de auditoría | `DOCS/P0_5_PARIDAD_ETIQUETAS.md` |
| Contrato de etiquetas en sombra | `motor/label_contract.py` |
| Auditoría reproducible | `tools/auditar_etiquetas.py` |
| Conteos y diferencias | secciones 5.1 y 5.2; `--json` |
| Cuatro jugadores | sección 4 |
| Muestras pequeñas y disponibilidad | secciones 4 y 5 |
| Pruebas de paridad y casos ambiguos | `motor/test_label_contract.py` |
| No cambio de etiquetas/recomendaciones | sección 7.4 |
| Commit y árbol limpio | se reportan al cerrar el bloque |

**Este bloque se detiene aquí.** No se activa el contrato, no se cambia ninguna
etiqueta efectiva y no se inicia otro bloque sin autorización explícita.
