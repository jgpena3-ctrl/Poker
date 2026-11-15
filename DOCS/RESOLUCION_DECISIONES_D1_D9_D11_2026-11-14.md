# Resolución de las decisiones D1–D9 y D11

**Fecha:** 2026-11-14  
**Tipo de trabajo:** revisión y resolución de decisiones. **No implementa** la política y **no modifica** tests, código, datos ni artefactos.  
**Base de referencia:** `data/hands_db.jsonl` en `HEAD = 3daf9d6f1b41a8d78bffc4c3be9b52d747a9fa96`, 1344 líneas, SHA-256 `3f0e7e5ea0d5c2d06aa9b8629817984ab9b4bccf057371823fde60370818262e`.  
**Snapshot histórico:** blob de `51a6fb9f05394fcfecd3b3ee4fb9479ed4e9600f:data/hands_db.jsonl`, 1253 líneas, 1,851,156 bytes, SHA-256 `c3172a147423d12a652767586dd76c36f24347c9dd503959dbea019e64944a09`; objeto Git `f52c09e294153e748f05d216bafcf6a779be4465`.  
**Documento de política que se revisa:** `DOCS/POLITICA_MANTENIMIENTO_TESTS_BASE_DINAMICA_2026-11-14.md`.

> Este documento no ejecuta una nueva auditoría general. Solo hace comprobaciones de lectura sobre las manos ambiguas y sobre la identidad del snapshot. No implementa cambios en tests, código, datos, matrices ni artefactos. PR-03 sigue bloqueado.

---

## 1. Resumen ejecutivo

Las decisiones que la política dejaba pendientes —D2–D9 y D11— se pueden resolver con la semántica del campo `amount`, la aritmética de los stacks y la distinción entre datos históricos y base actual. En particular, los cinco valores que bloqueaban los casos 6, 7, 10, 15 y 16 quedan adjudicados. La revisión produce una separación que la política anterior no tenía:

| Población | Total de calls cortas | All-in por menos | Frame intermedio | Corta con fichas detrás |
|---|---:|---:|---:|---:|
| Base actual (1344) | 47 | 41 | 2 | 4 |
| Snapshot histórico (1253) | 42 | 39 | 0 | 3 |
| Manos nuevas (91) | 5 | 2 | 2 | 1 |

La consecuencia principal es que **el 42 histórico nunca fue “42 defectos”**: 39 de las 42 son all-in por menos, y solo 3 son calls cortas con fichas detrás. En la base actual, las 47 se descomponen en 41 all-in, 2 frames de captura y 4 calls cortas reales. Las cinco calls nuevas son exactamente:

- `H_1303` turn SB 3.9: **all-in por menos**; la SB agota sus 10.3 y está marcada en `allin` como `p5`.
- `H_1365` flop SB 83.9: **all-in por menos**; la SB agota sus 112.9, el BB también está all-in y marcado como `p2`, pero la SB no está marcada.
- `H_1310` preflop SB 1.0 y flop SB 4.3: **frames intermedios**; la misma SB completa la viva en la misma calle con 3.0 y 4.4. No son dos defectos.
- `H_1287` preflop CO 1.0: **corta con fichas detrás**; el CO tiene 20.0 de stack y luego foldea. Es la única call corta nueva que es un defecto de lectura/secuencia.

Además:

- El par SB/BB de `H_0104` (−8) y `H_1365` (−28) no son diferencias de caja: comparan calls en niveles distintos; las manos acaban con uno o ambos jugadores all-in. El −2 de `H_1310` es un frame. La métrica de “primera call de cada posición” no tiene ninguna señal válida.
- `H_1349` tiene `stack: null`; se trata como **desconocido**, no como cero. No hay violación I4 nueva. La única violación I4 real sigue siendo `H_0740` SB 28.2 > 28.1.
- El snapshot histórico **no puede ser “las primeras 1253 líneas del fichero actual”**: los 1253 IDs coinciden, pero 127 manos tienen contenido distinto respecto del blob de `51a6fb9`. Los 22 agregados coinciden hoy, pero la procedencia inmutable es el blob, no el corte de líneas.
- D1–D7 y D9 quedan resueltas técnicamente. D8 (gobierno del ledger) está **pendiente de ratificación**; D11 (autorización de PR-03) sigue bloqueada. PR-03 no se autoriza en este documento.

### 1.1 Reparto actualizado de recomendaciones

| Recomendación primaria | Casos | Nº |
|---|---|---:|
| `CONSERVAR_SNAPSHOT` | 8 | 1 |
| `CONVERTIR_A_INVARIANTE` | 1, 2, 3, 4, 5, 9, 10, 11, 12, 16, 17, 18, 19, 21, 22 | 15 |
| `DEFINIR_SUBCONJUNTO` | 13, 14 | 2 |
| `REEMPLAZAR_POR_FIXTURE` | 20 | 1 |
| `CONVERTIR_A_LEDGER` | 6, 15 | 2 |
| `REEMPLAZAR_POR_INVARIANTE` | 7 | 1 |
| `REQUIERE_DECISION_MANUAL` | ninguno | 0 |

La categoría `REQUIERE_DECISION_MANUAL` desaparece porque las cinco decisiones que la sostenían están resueltas. Lo que queda es ratificar el gobierno del ledger (D8) y la autorización de PR-03 (D11), no volver a decidir la semántica de las manos.

---

## 2. Evidencia de esta revisión

### 2.1 La semántica de `amount`

`recorder/record_hand.py` fija que `amount` es la **caja acumulada de la calle**, no el delta y no el tamaño objetivo. La auditoría ya lo documentó y `AO.aportar_por_jugador` lo aplica: la aportación de un jugador en una calle es el **último** valor de su caja en esa calle, no la suma de sus acciones.

De ahí se sigue la definición que resuelve las manos ambiguas:

```text
aportado_acumulado(h, pos, calle) =
    suma, para cada calle hasta `calle` inclusive,
    del último `b`/`c`/`r` de `pos` en esa calle
```

Un jugador está all-in por menos cuando:

1. su stack es conocido;
2. `aportado_acumulado` es igual a su stack inicial (tolerancia 0.05);
3. no tiene ninguna acción de aportación posterior.

Eso no es una hipótesis: es la definición de “puso todo lo que tenía”. Si además la call no alcanza la viva, es una **all-in por menos**, no una lectura corta.

### 2.2 Comprobaciones de lectura realizadas

Sin escribir en la base:

| Comprobación | Resultado |
|---|---|
| Calls cortas actuales | 47 |
| De ellas, all-in por menos | 41 |
| De ellas, frames intermedios | 2 (`H_1310` preflop y flop) |
| De ellas, cortas con fichas detrás | 4 (`H_0589`, `H_0740` BB, `H_0740` CO, `H_1287` CO) |
| Calls cortas históricas | 42 |
| De ellas, all-in por menos | 39 |
| De ellas, cortas con fichas detrás | 3 (`H_0589`, `H_0740` BB, `H_0740` CO) |
| Calls cortas nuevas | 5 = 2 all-in (`H_1303`, `H_1365`) + 2 frames (`H_1310` ×2) + 1 corta real (`H_1287`) |
| All-in actuales sin acción posterior | 41 de 41 |
| I4 real | `H_0740` SB 28.2 > 28.1, única |
| I4 no evaluable | 12 stacks desconocidos (11 históricos + `H_1349`) |
| `falta` de bote | 3 IDs: `H_0357`, `H_0589`, `H_0740` (iguales en 1253 y 1344) |
| Blob 51a6fb9 vs primeras 1253 líneas actuales | mismos 1253 IDs; 127 manos con contenido distinto; bytes distintos |
| Agregados de los 22 tests | idénticos con el blob y con el subconjunto actual de 1253 IDs |

Identidad Git verificada en modo lectura: `git rev-parse 51a6fb9` devuelve `51a6fb9f05394fcfecd3b3ee4fb9479ed4e9600f`; `git cat-file -t` devuelve `commit`; `git ls-tree` encuentra `data/hands_db.jsonl` como objeto `f52c09e294153e748f05d216bafcf6a779be4465`. `git show 51a6fb9:data/hands_db.jsonl` produce exactamente 1,851,156 bytes, 1253 líneas y SHA-256 `c3172a147423d12a652767586dd76c36f24347c9dd503959dbea019e64944a09`.

### 2.3 Corrección de dos afirmaciones previas

La revisión corrige dos afirmaciones que la política anterior usaba para dejar casos abiertos:

1. **`H_1303`: el campo `allin` sí marca a la SB.** El mapeo es `players[PLAYER_IDS.index(x)]`, con `PLAYER_IDS = ('hero','p1','p2','p3','p4','p5')`. En `H_1303`, `p5` es `players[5]`, la SB `Tonytruco`. No es el CO ni “otro jugador”. La SB está marcada y su aportación acumulada es exactamente 10.3. La afirmación “sin all-in del SB” era incorrecta.
2. **`H_1365`: el campo `allin` marca al BB, no a la SB.** `p2` es `players[2]`, el BB `Elperron`, que también agota su stack (29.0 + 84.6 = 113.6). La SB es `hero` (`players[0]`) y agota 112.9 sin marca. No hay contradicción: hay una **omisión** de un all-in, exactamente la clase que B1-E §4.7 documenta.

También se corrige una afirmación metodológica de la política anterior:

3. **Los conjuntos de rake no particionan la base.** `sin_rake=394` y `con_rake=270` suman 664, no 1344. Son dos recuentos independientes de coincidencia, no una partición. El invariante correcto es `con_rake < sin_rake` y ambos positivos; los recuentos se reportan.

Y una lectura que el nombre del test inducía:

4. **Las 42 calls históricas no son 42 defectos.** Son 39 all-in por menos + 3 calls cortas con fichas detrás. El docstring del caso 15 (“la normalización redujo el defecto de 498 a 42”) describe el recuento bruto del detector, no un recuento de defectos.

---

## 3. Semántica de las manos ambiguas

### 3.1 Algoritmo de clasificación

Para que las mismas manos no reciban nombres distintos en casos 6, 7, 10, 15, 16 y 17, la clasificación debe vivir en **un solo helper**, usado por el detector de calls cortas y por el clasificador de aportaciones:

```text
para cada call `c` de `pos` en `calle`:
    st = stack de `pos` (None si desconocido)
    cum = aportado_acumulado(h, pos, calle)
    posteriores = acciones de aportación de `pos` después de esta acción

    si st es None:
        tipo = DESCONOCIDO
    si no:
        si abs(cum - st) <= 0.05 y no posteriores:
            tipo = ALLIN_CORTO
        si hay una acción posterior en la misma calle con importe mayor
           y el valor final de la calle alcanza la viva:
            tipo = FRAME_INTERMEDIO
        si no:
            tipo = CORTA_CON_FICHAS
```

Reglas:

- `ALLIN_CORTO` es una jugada legítima: el jugador puso todo su stack y no pudo igualar la viva. No es un defecto.
- `FRAME_INTERMEDIO` es una lectura intermedia de la misma call; la call real es el valor final de la calle. No es un defecto separado.
- `CORTA_CON_FICHAS` es la única clase que entra en el ledger de calls cortas como anomalía: el jugador tenía fichas y no alcanzó la viva, o la secuencia es imposible.
- `DESCONOCIDO` no se clasifica como defecto ni como all-in; se reporta como no evaluable.

### 3.2 `H_1303` — all-in por menos, marcado

| Campo | Valor |
|---|---|
| SB | `Tonytruco`, `p5`, stack 10.3 |
| Preflop SB | `p 0.5`, `r 2.0` → caja 2.0 |
| Flop SB | `c 4.4` → caja 4.4 |
| Turn SB | `c 3.9` frente a viva 6.2 |
| Acumulado | 2.0 + 4.4 + 3.9 = **10.3 = stack** |
| Acciones posteriores de la SB | ninguna |
| `allin` | `['p5']` → `players[5]` = SB |
| `final_pot` | 29.0; B1-E lo confirma y limita `recorder_audit.pot_*` |

**Lectura:** la SB se juega el stack en el turn. La call de 3.9 es corta respecto de 6.2 porque no tenía más. Es un all-in por menos, está marcado y es coherente. **No es un defecto de call corta ni una mano sin adjudicar.** Pasa al ledger como `ALLIN_CORTO`.

La diferencia de 0.3 entre la suma de aportaciones (29.3) y el `final_pot` (29.0) es una limitación de bote ya documentada por B1-E; no cambia la clasificación de la call.

### 3.3 `H_1365` — dos all-in, uno marcado y otro omitido

| Jugador | Stack | Aportación acumulada | Marca `allin` |
|---|---:|---:|---|
| SB `Jarduan` (`hero`) | 112.9 | 29.0 + 83.9 = **112.9** | no |
| BB `Elperron` (`p2`) | 113.6 | 29.0 + 84.6 = **113.6** | sí |
| CO `Jhon. As` | 87.8 | 0.0 (fold preflop) | no |

Secuencia del flop: SB `b 57.0`, BB `r 84.6`, SB `c 83.9`.

**Lectura:** el BB sube a 84.6, que es todo su stack restante; la SB solo tiene 83.9 y llama con todo. Es un enfrentamiento de dos all-in, con la SB por menos. La call de 83.9 es legítima. El campo `allin` marca al BB y omite a la SB; B1-E §4.7 incluye `H_1365` precisamente entre las 23 manos con un all-in sin marca. **No es un defecto de call corta.** Pasa al ledger como `ALLIN_CORTO`, con la nota `allin_omitido: SB`.

La diferencia de 0.9 entre aportaciones (226.5) y `final_pot` (225.6) es una limitación de bote ya documentada; no cambia la clasificación.

### 3.4 `H_1310` — dos frames, una sola call por calle

| Calle | Secuencia de la SB | Viva | Valor final | Lectura |
|---|---|---|---:|---|
| Preflop | `c 1.0`, luego `c 3.0` | 3.0 | 3.0 | Frame intermedio; la call real es 3.0 |
| Flop | `c 4.3`, luego `c 4.4` | 4.4 | 4.4 | Frame intermedio; la call real es 4.4 |
| Turn | `c 13.2` | 13.1 | 13.2 | No es corta; es un exceso de 0.1, otra anomalía de lectura |

La SB no está all-in: su stack es 92.4 y su aportación acumulada es 20.6. B1-E ya declara `H_1310` con “llamadas duplicadas en preflop y flop” y la excluye de secuencia y frecuencias.

**Lectura:** las dos calls “cortas” son frames de la misma call; la misma posición completa la viva en la misma calle. Contarlas como dos defectos infla el detector. Se registran como `FRAME_INTERMEDIO` en el ledger de diagnóstico, no en el de calls cortas reales. La mano sigue excluida de secuencia/frecuencias por B1-E; no se excluye del registro.

### 3.5 `H_1349` — stack desconocido, no cero

| Campo | Valor |
|---|---|
| UTG `LaloMora` | `stack: None`, `active: true` |
| Aportación | 3.0 (preflop `c 1.0` y `c 2.0`; turn `c 1.0`) |
| Valor derivado B1-E | 45.9, **no canónico** |
| `final_pot` | 19.7, confirmado por B1-R; bote `NADA` |

**Lectura:** el stack es desconocido. No se compara con la aportación; se cuenta en `I4_no_evaluable` con ID. No se escribe 45.9 en la base; no se convierte `None` en 0.0. Si en el futuro el propietario corrige el dato, se actualiza el manifiesto y el ledger, y `H_1349` sale de no evaluable. **No es una violación I4.**

### 3.6 `H_0104` — el −8 histórico es un all-in en otro nivel

| Campo | SB | BB |
|---|---|---|
| Primera call | 1.0 | 9.0 |
| Viva de esa call | 1.0 | 9.0 |
| Stack | 25.7 | 9.7 |
| Acumulado | 1.0 | 9.0 + 0.7 = **9.7 = stack** |
| `allin` | no | `p5` → BB |

La SB llama 1.0 cuando la viva es 1.0; el BB llama 9.0 cuando la viva es 9.0. Con la call de 0.7 del flop, el BB agota sus 9.7; la mano acaba con el BB all-in. No son dos ciegas equivalentes: son decisiones en niveles distintos. El −8 no es una diferencia de caja entre ciegas; es un artefacto de la definición “primera call de cada posición”.

### 3.7 Las cuatro calls cortas reales

| Mano | Calle | Pos | Amount | Viva | Falta | Stack | Acumulado | Contexto |
|---|---|---|---:|---:|---:|---:|---:|---|
| `H_0589` | preflop | BB | 5.9 | 6.9 | 1.0 | 37.9 | 5.9 | Tiene fichas; no hay all-in; `final_pot` tiene `falta` 0.7 |
| `H_0740` | preflop | BB | 1.0 | 2.0 | 1.0 | 136.0 | 1.0 | Tiene fichas; la SB subió a 2.0; `falta` de bote 0.9 |
| `H_0740` | preflop | CO | 1.0 | 2.0 | 1.0 | 183.6 | 1.0 | Tiene fichas; mismo nivel que el BB; `falta` de bote 0.9 |
| `H_1287` | preflop | CO | 1.0 | 6.0 | 5.0 | 20.0 | 1.0 | Tiene fichas; después foldea; B1-E la declara secuencia imposible |

Las cuatro son **observaciones confirmadas** de call corta con fichas detrás. La causa individual no está adjudicada para `H_0589` ni para `H_0740`; `H_1287` sí está declarada secuencia imposible por B1-E. El ledger debe distinguir `observación` de `causa`:

- `estado`: `CONFIRMADA`.
- `causa`: `SECUENCIA_IMPOSIBLE` (`H_1287`) o `NO_ADJUDICADA` (`H_0589`, `H_0740`).
- `evidencia`: la tabla anterior y, cuando exista, la `falta` de bote.

`H_0740` es un caso con tres síntomas independientes: dos calls cortas, una violación I4 de 0.1 y una `falta` de bote de 0.9. Se registran por separado; no se suman en un “defecto único” ni se corrigen por conveniencia.

### 3.8 `H_0058` — el fixture sigue siendo válido, pero es un all-in

La secuencia del river es `BB x 0.0`, `MP b 15.3`, `BB c 9.1`. El BB tiene stack 19.6 y acumula 19.6; la call de 9.1 es un all-in por menos. El fixture literal del caso 6 se conserva como ejemplo de secuencia y de lectura de caja, pero su clasificación es `ALLIN_CORTO`, no “defecto”. El ledger histórico lo incluye entre los 39 all-in.

### 3.9 Reconciliación de los recuentos

| Clase | Histórico 1253 | Actual 1344 | Nuevas 91 |
|---|---:|---:|---:|
| `ALLIN_CORTO` | 39 | 41 | 2 (`H_1303`, `H_1365`) |
| `FRAME_INTERMEDIO` | 0 | 2 | 2 (`H_1310` ×2) |
| `CORTA_CON_FICHAS` | 3 | 4 | 1 (`H_1287`) |
| **Total calls cortas** | **42** | **47** | **5** |

El delta 42 → 47 es exactamente 2 all-in + 2 frames + 1 corta real. No hay una quinta “corta real” escondida.

### 3.10 Efecto sobre la conclusión cualitativa del caso 16

Con la clasificación corregida, las calls cortas reales por posición son:

| Posición | Histórico | Actual |
|---|---:|---:|
| BB | 2 | 2 |
| CO | 1 | 2 |
| MP | 0 | 0 |
| UTG | 0 | 0 |
| BTN | 0 | 0 |
| SB | 0 | 0 |
| **Total** | **3** | **4** |

- `uno = 3` sigue siendo verdadero: las tres históricas tienen `falta` 1.0.
- `BB = 2`, no 10. El 10 histórico contaba all-in de BB como si fueran calls cortas.
- La conclusión “no es solo del BB” **sigue siendo verdadera** porque hay CO.
- La conclusión “hay calls cortas en las seis posiciones” **es falsa** como afirmación de defectos. Las calls de MP/UTG/BTN/SB del recuento bruto son all-in o frames, no calls cortas con fichas detrás.

El test del caso 16 debe conservar la propiedad que sobrevive (`BB < len(calls)` y `CO > 0`) y reportar `uno=3`, `BB=2`, no la foto de seis posiciones.

---

## 4. Política de snapshots

### 4.1 Qué es un snapshot

Un snapshot es una **población histórica inmutable**, no una vista de la base actual. Se identifica por:

- `path` y `commit` del blob original;
- `sha256` del contenido;
- número de líneas;
- población y regla de selección;
- versión del código o del contrato que produjo las métricas;
- métricas esperadas, aprobadas por una persona.

El test verifica el hash **antes** de leer. Si el snapshot no está disponible o el hash no coincide, falla; no cae en silencio a la base actual.

### 4.2 El snapshot de 1253 no es “las primeras 1253 líneas”

La comprobación es decisiva:

| Fuente | Líneas | SHA-256 | ¿Mismos IDs? | ¿Mismos bytes? |
|---|---:|---|---|---|
| Blob `51a6fb9:data/hands_db.jsonl` | 1253 | `c3172a14…` | — | — |
| Primeras 1253 líneas del fichero actual | 1253 | `3cfe9be7…` | sí | **no** |
| Subconjunto actual por los 1253 IDs históricos | 1253 | — | sí | **no** |

Hay **127 manos** de los 1253 IDs históricos con contenido distinto en el fichero actual (campos `showdown`, `streets`, `players`, `winner`). Hoy los 22 agregados coinciden con el blob y con el subconjunto actual; pero eso es una coincidencia verificada, no una garantía. Una corrección manual futura podría cambiar un agregado y el corte de líneas la seguiría en silencio.

Por tanto:

- **La fuente del snapshot es el blob de `51a6fb9`**, no un corte del fichero actual.
- El snapshot se guarda como fixture de test inmutable, con su hash y su número de líneas.
- El subconjunto actual de 1253 IDs puede usarse como control de reconciliación, nunca como snapshot.

### 4.3 La base actual no es un snapshot

La base actual es la fuente dinámica. Se lee a través del manifiesto `HANDS_DB_*`:

- `HANDS_DB_COMMIT='8594ed5'`;
- `HANDS_DB_SHA256='3f0e7e5e…'`;
- `HANDS_DB_LINEAS=1344`.

El test comprueba que el hash del disco coincide con el manifiesto antes de medir. Si no coincide, falla. Un cambio de datos exige actualizar el manifiesto en el mismo cambio, con revisión humana. No se crea un snapshot nuevo en cada crecimiento; el snapshot se crea solo cuando hay una razón de preservación histórica.

### 4.4 Dónde se guarda el snapshot

**Recomendación: fixture comprometido en el repositorio, no `git show` en tiempo de test.**

- `tests/data/snapshots/hands_1253_51a6fb9.jsonl` (1.85 MB) o equivalente.
- Un manifiesto pequeño `tests/data/snapshots.json` con `id`, `path`, `commit`, `sha256`, `lineas`, `purpose`, `created`, `owner`, `metrics_version`.
- El fixture se lee una vez por sesión (`scope="session"`) y se verifica su hash.
- Si el fixture falta o el hash no coincide, el test falla; no se salta.

Por qué no `git show` en cada test:

- un clon superficial o un export sin `.git` no puede recuperar el blob;
- el test dependería del historial y de la configuración de git;
- el fixture es reproducible, hasheable y no depende de la red ni del clon.

El coste es 1.85 MB, aceptable para un repositorio de 2.07 MB de datos. La suite actual tarda segundos; la lectura única no es un problema.

### 4.5 Snapshot de datos y versión del código

Un snapshot tiene dos capas:

1. **Datos**: el blob inmutable y sus métricas dependientes solo del dato (número de manos, posiciones, ciegas, calls, botes).
2. **Comportamiento**: las métricas que dependen de una función del motor (`clasificar_aportado`, `aportar_por_jugador`, `_es_ciega_bb`, `get_position`, el detector de viva).

La política debe registrar `code_commit` o `metrics_version` junto a las métricas. Ejemplo:

```text
snapshot_id: s1253-51a6fb9
data_sha256: c3172a14…
data_lineas: 1253
metrics_version: detector-v1 / classifier-v1 / pot-v1
```

Consecuencia importante: **la corrección del all-in acumulado cambia los totales del clasificador**. El clasificador actual, aplicado al snapshot 1253, da 5001/29/23; con la corrección estimada daría 5035/16/2 (matriz 5053). En la base actual 1344, el clasificador actual da 5417/33/26; con la corrección estimada daría 5453/19/4 (matriz 5476). Son dos poblaciones distintas y no se mezclan. Eso no es un cambio de datos: es un cambio de contrato de código. El snapshot de datos sigue siendo el mismo; la versión de métricas cambia y se revisa.

Regla:

- Un cambio de datos no cambia el snapshot histórico; cambia el manifiesto de la base actual.
- Un cambio de código puede cambiar las métricas del snapshot; se registra una nueva `metrics_version`, se revisan las diferencias y se aprueba. No se sobreescriben los valores antiguos en silencio.
- Los valores antiguos se conservan en el historial del snapshot o en el documento de cierre.

### 4.6 Correcciones manuales de manos históricas

La corrección manual es un canal legítimo y debe preservarse:

1. El propietario corrige la mano en `data/hands_db.jsonl` a mano.
2. En el mismo cambio, actualiza `HANDS_DB_COMMIT`, `HANDS_DB_SHA256` y `HANDS_DB_LINEAS`.
3. Añade una nota en `DOCS/` con `hand_id`, campo, valor anterior, valor nuevo, motivo y fecha.
4. Si la corrección resuelve o crea una anomalía, actualiza el ledger de la base actual con evidencia.
5. **No edita el snapshot histórico.** El snapshot conserva el estado anterior; eso es su función.
6. Si se quiere un nuevo baseline histórico, se crea un **nuevo** snapshot con un nuevo `snapshot_id` y su commit; no se reescribe el anterior.

Ningún script corrige, reescribe o “arregla” la base para que pase un test. La revisión manual sigue siendo la única vía.

### 4.7 Registro de snapshots y ledgers

Esquema mínimo propuesto (los nombres son ilustrativos; no se crean ficheros en esta tarea):

```json
{
  "snapshots": [
    {
      "id": "s1253-51a6fb9",
      "path": "tests/data/snapshots/hands_1253_51a6fb9.jsonl",
      "source_path": "data/hands_db.jsonl",
      "commit": "51a6fb9",
      "sha256": "c3172a147423d12a652767586dd76c36f24347c9dd503959dbea019e64944a09",
      "lineas": 1253,
      "purpose": "Expectativas historicas de los 22 tests",
      "created": "2026-11-14",
      "owner": "propietario del repositorio",
      "metrics_version": "v1"
    }
  ]
}
```

```json
{
  "short_calls": [
    {
      "hand_id": "H_0589",
      "calle": "preflop",
      "indice": 5,
      "pos": "BB",
      "amount": 5.9,
      "viva": 6.9,
      "tipo": "CORTA_CON_FICHAS",
      "estado": "CONFIRMADA",
      "causa": "NO_ADJUDICADA",
      "evidencia": "stack 37.9; sin accion posterior; falta de bote 0.7"
    }
  ],
  "allin": [
    {
      "hand_id": "H_1303",
      "calle": "turn",
      "pos": "SB",
      "amount": 3.9,
      "viva": 6.2,
      "stack": 10.3,
      "acumulado": 10.3,
      "marcado_en_allin": true,
      "estado": "ALLIN_CORTO"
    }
  ],
  "frames": [
    {
      "hand_id": "H_1310",
      "calle": "preflop",
      "pos": "SB",
      "amount": 1.0,
      "viva": 3.0,
      "valor_final": 3.0,
      "estado": "FRAME_INTERMEDIO"
    }
  ]
}
```

Reglas de gobierno (D8):

- El ledger es un fichero versionado de datos de test, no un comentario.
- Cada entrada tiene `hand_id`, localización, importe, viva, tipo, estado, causa y evidencia.
- El test compara el detector con el ledger **exactamente**. Una anomalía nueva falla.
- Añadir una entrada exige una revisión humana y un diff visible; no se genera automáticamente.
- Quitar una entrada exige evidencia de que la anomalía desapareció (corrección de dato o cambio de contrato) y una nota de baja.
- El aprobador es el propietario del repositorio. En un repositorio individual, la aprobación se registra en el mensaje del commit o en el documento de cierre.
- Un generador puede proponer un diff; no puede escribirlo sin revisión.

### 4.8 Dónde se ejecuta el snapshot

- **Suite habitual:** sí. El snapshot 1253 es rápido y barato; su presencia continua evita que el histórico se degrade.
- **Marcador:** `@pytest.mark.snapshot`, incluido por defecto. Se puede excluir en un bucle rápido con `-m "not snapshot"`, pero la ejecución completa lo incluye.
- **Job separado:** no es necesario hoy; si el fixture crece o el coste sube, se puede mover a un job de snapshots sin perder la puerta de aprobación.

### 4.9 Qué no se debe hacer

- No usar las primeras N líneas del fichero actual como snapshot.
- No usar `load_hands(reliable_only=True)` como procedencia: su ventana de 900 líneas es una regla de calibración, no un corte histórico.
- No usar `H_1014` o `H_1282` como límite de línea para una cohorte.
- No reducir la base a 1253 para que pasen los tests.
- No actualizar los 22 números en masa.
- No convertir `stack: null` en `0.0`.
- No convertir un snapshot histórico en la base actual por comodidad.
- No aceptar una call corta nueva sin ledger.
- No borrar un diagnóstico para que la suite pase.
- No reescribir un snapshot para que coincida con una corrección manual.

---

## 5. Resolución de D1–D9 y D11

### 5.1 Tabla de decisiones

| ID | Decisión | Resolución | Evidencia | Estado |
|---|---|---|---|---|
| D1 | ¿La base canónica para los tests es 1344, con 1253 como snapshot histórico? | **Sí.** 1344 es la base dinámica actual, identificada por el manifiesto. 1253 es un snapshot histórico inmutable del blob `51a6fb9`. Ningún test fija 1344 como literal; los invariantes leen el total de la fuente. | Manifiesto `HANDS_DB_*`; hash `3f0e7e5e…`; blob `c3172a14…` | Resuelta |
| D2 | ¿Una call corta que iguala el stack acumulado es all-in corto legítimo? | **Sí.** Si el stack es conocido, el acumulado es igual al stack y no hay acción posterior, es un all-in por menos. No es un defecto. `H_1303` y `H_1365` quedan adjudicadas como `ALLIN_CORTO`. | 41/47 actuales y 39/42 históricas; `H_1303` marcada `p5`; `H_1365` SB omitida, BB marcada `p2`; B1-E §4.7 | Resuelta |
| D3 | ¿Cómo se tratan las calls duplicadas de `H_1310`? | **Una sola call por jugador y calle, con el valor final.** Las actions 1.0→3.0 y 4.3→4.4 son frames de la misma call; no son dos defectos. La mano sigue excluida de secuencia/frecuencias por B1-E. | Secuencia de `H_1310`; B1-E “llamadas duplicadas”; valor final 3.0 y 4.4 alcanza la viva | Resuelta |
| D4 | ¿`stack: null` se excluye, se cuenta aparte o se corrige con 45.9? | **Se cuenta aparte como desconocido.** No se compara, no se convierte en 0.0 y no se escribe 45.9. `H_1349` entra en `I4_no_evaluable`; la única violación I4 real es `H_0740` SB. | 12 desconocidos actuales = 11 históricos + `H_1349`; B1-E §4.8; `H_0740` 28.2 > 28.1 | Resuelta |
| D5 | ¿El par SB/BB se define por misma viva o por primera call de cada posición? | **Por misma viva, y además la comparación de par se retira como contrato.** La propiedad válida es “cada call alcanza la viva o es all-in/frame/ledger”. `H_0104` y `H_1365` no se emparejan; `H_1310` es frame; no queda ninguna diferencia de par válida. | `H_0104` SB 1.0/viva 1.0 vs BB 9.0/viva 9.0 (niveles distintos; la mano acaba con el BB all-in); `H_1365` SB 1.0/viva 1.0 vs BB 29.0/viva 29.0 (niveles distintos; la mano acaba con ambos all-in); `H_1310` frame | Resuelta |
| D6 | ¿Se conserva el snapshot 1253 en la suite habitual? | **Sí.** Como fixture inmutable, con hash verificado y lectura por sesión. Es barato y evita que el histórico se degrade. Se marca `snapshot`; se incluye por defecto. | 1253 líneas, 1.85 MB; suite actual de segundos; 22 agregados reproducidos | Resuelta |
| D7 | ¿La ausencia de `allin` es huella suficiente de `record_hand`? | **Solo para la cohorte histórica cerrada de 71 IDs.** No es una regla general de procedencia. Las manos nuevas se clasifican por commit/fuente explícita, no por ausencia del campo. El campo `allin` tampoco es señal exhaustiva de all-in. | 71 IDs exactos; `record_hand.py` no escribe `allin`; 23 all-in sin marca en B1-E §4.7 | Resuelta con matiz |
| D8 | ¿Quién aprueba un ledger y cómo se añade/quita una entrada? | **Propuesta pendiente de ratificación:** propietario del repositorio, revisión humana y diff visible. Nueva anomalía falla; alta/baja documentada con evidencia; sin auto-update. | Política de ledgers §4.7; repo individual | **Pendiente de ratificación** |
| D9 | ¿Se actualiza el censo 2702 de `p` como snapshot 1344 o se mantiene 1253? | **Ni una cosa ni la otra como literal.** El censo 2522 va al snapshot 1253; la base actual se cubre con un invariante (`p` solo preflop, toda ciega con `p`, ningún `p` postflop). 2702 se reporta, no se fija. | 2522 histórico; 2702 actual; 0 `p` postflop; todas las ciegas con `p` | Resuelta |
| D11 | ¿Cuándo se autoriza PR-03? | **Solo después de la puerta G1–G5 y de una autorización explícita del propietario.** Este documento no autoriza PR-03. | Fases 0–6 de la política; suite verde por contratos | Bloqueado; requiere autorización |

### 5.2 D1 — base canónica y snapshot

La base canónica para los tests es la base actual adoptada, 1344, leída a través del manifiesto. El snapshot 1253 es una población histórica separada. No se mezclan:

- los invariantes actuales se ejecutan sobre 1344 y fallan si el hash del disco no coincide con el manifiesto;
- el snapshot se ejecuta sobre el fixture de 1253 y falla si su hash no coincide;
- ningún test usa “las primeras 1253 líneas” como sustituto del snapshot.

### 5.3 D2 — all-in por menos

La regla es aritmética, no interpretativa. Si el jugador puso todo su stack y no actuó después, es un all-in por menos. La call corta es la consecuencia, no el defecto. Los 41 casos actuales cumplen la regla; los 39 históricos también. `H_1303` y `H_1365` no son excepciones.

El campo `allin` se usa solo como corroboración:

- `H_1303`: `p5` = SB, marcada; corrobora.
- `H_1365`: `p2` = BB, marcada; la SB está omitida; B1-E §4.7 la documenta; la aritmética manda.
- `H_1287`: `p4` = MP, marcada; el MP es el all-in; la corta real es el CO, que no es all-in.

### 5.4 D3 — frames de captura

El grabador emite una acción cuando la caja cambia; una animación de caja puede producir dos lecturas de la misma call. La lectura correcta es el valor final de la calle. `H_1310` es el caso claro: la misma SB pasa por 1.0 y 3.0 en preflop, y por 4.3 y 4.4 en flop. El valor final alcanza la viva. Contar dos defectos es un falso positivo.

La mano sigue excluida de secuencia/frecuencias por B1-E; esa exclusión es independiente de la clasificación de la call. El ledger de frames es diagnóstico, no una lista de defectos.

### 5.5 D4 — stack desconocido

El contrato es:

- `stack` numérico, incluido `0.0`: conocido. Si la aportación lo supera, es violación.
- `stack` `None`, ausente o no numérico: desconocido. No se compara; se cuenta en `I4_no_evaluable` con ID.
- Prohibido `float(p.get('stack') or 0.0)` para stacks.

El resultado actual con este contrato:

```text
I4_violaciones = {('H_0740', 'SB', 28.2, 28.1)}   # 1
I4_no_evaluable = 12 IDs (11 históricos + H_1349)
I2 = 3
I1 = true
```

No se fija `I4=12` ni `I4=13`. Se fija el conjunto de violaciones y el conjunto de no evaluables. Si `H_1349` se corrige a 45.9 en el futuro, sale de no evaluable y no hay violación nueva; si se deja como está, sigue siendo desconocido.

### 5.6 D5 — misma viva y retirada del par

La comparación válida es:

- cada call se contrasta con la viva del momento;
- si se emparejan SB y BB, solo se emparejan calls de la misma calle que afrontan la misma `viva_antes`;
- ambas deben alcanzar la viva o ser all-in/frame/ledger;
- no se usa `sb[0]`/`bb[0]` como equivalencia.

Con los datos actuales, la métrica de par no tiene ninguna diferencia válida:

- `H_0104`: SB 1.0 en viva 1.0; BB 9.0 en viva 9.0. Niveles distintos; la mano acaba con el BB all-in. No se emparejan.
- `H_1365`: SB 1.0 en viva 1.0; BB 29.0 en viva 29.0. Niveles distintos; la mano acaba con ambos all-in. No se emparejan.
- `H_1310`: SB 1.0→3.0 y 4.3→4.4; frames; la call final alcanza la viva. No hay defecto de par.

Por eso el test del caso 7 no se “actualiza a 60” ni conserva −8/−28 como conocidos. Se sustituye por el invariante por call + el ledger. La comparación de par puede quedar como diagnóstico secundario, pero no como contrato.

### 5.7 D6 — snapshot en la suite habitual

Se conserva. Es la única forma de que una corrección manual futura no borre la referencia histórica. El coste es bajo. El snapshot se lee una vez por sesión y se verifica su hash. La suite completa lo incluye; el marcador `snapshot` permite excluirlo en un bucle rápido, pero la puerta de cierre lo exige.

### 5.8 D7 — cohorte de 71 y huella de grabador

La ausencia de `allin` es una huella **histórica** válida para las 71 manos de `record_hand`, porque el código de `record_hand.py` no escribe el campo y el de `recorder_live.py` sí. Pero:

- la cohorte se define por **IDs exactos**, no por “ausencia de `allin`” en general;
- una mano nueva sin `allin` no se añade automáticamente a la cohorte; es una señal para revisar la procedencia;
- el campo `allin` no es exhaustivo: puede omitir un all-in (`H_1365` SB); no se usa como única señal.

La cohorte de 71 es: `H_0001`..`H_0073` menos `H_0028` y `H_0072`. Se contrasta por conjunto exacto.

### 5.9 D8 — gobierno del ledger (pendiente de ratificación)

El ledger es la expectativa, no una lista de excusas. Para que no se degrade:

- cada entrada tiene ID, localización, importe, viva, tipo, estado, causa y evidencia;
- el test compara exactamente; una anomalía nueva falla;
- alta y baja requieren revisión humana y diff visible;
- el aprobador es el propietario;
- no hay auto-update;
- el generador puede proponer, no escribir.

Este documento propone el proceso; la ratificación del propietario es la que lo activa.

### 5.10 D9 — censo de `p`

El censo 2522 es histórico. El censo 2702 es actual. Ninguno de los dos debe ser un literal frágil en un test de la base actual.

Diseño:

- **Snapshot 1253:** `p` total 2522; todas preflop; sin `p` postflop.
- **Invariante actual:** toda acción `p` es preflop; toda SB/BB tiene su `p` con 0.5/1.0; no hay `p` en flop/turn/river; el número de `p` se reporta (2702), no se fija.
- Si el propietario quiere un censo actual exacto, se crea un snapshot `canonical-1344` con 2702 y un `snapshot_id` nuevo; no se edita el 2522. No es la recomendación: el invariante es más fuerte y no envejece con el crecimiento.

### 5.11 D11 — puerta de PR-03

PR-03 no se autoriza aquí. La puerta propuesta es:

Ninguna puerta se considera satisfecha por la mera existencia de este documento ni por defecto. Cada una necesita la evidencia indicada y comienza como `NO SATISFECHO`:

| Puerta | Criterio verificable | Evidencia exigida para pasar | Estado comprobado |
|---|---|---|---|
| G1 | Los 22 casos tienen contrato y diseño de resolución aprobado (A–E, primario/secundario), sin `REQUIERE_DECISION_MANUAL`. | Matriz de 22 casos revisada y aprobación explícita del propietario registrada en el cierre. | **NO SATISFECHO** — hay diseño documental; no consta aprobación de cierre. |
| G2 | Descriptores de snapshot, cohorte y ledger existen y son válidos; hashes y membresías se verifican. | Archivos implementados; ejecución automatizada que valida SHA/line count del snapshot y conjuntos exactos de cohortes/ledgers, con salida registrada. | **NO SATISFECHO** — no se han creado los descriptores/fixtures ni ejecutado su validador. |
| G3 | La suite completa queda verde por contratos, no por tests eliminados o debilitados. | Comando de suite completa, salida con cero fallos y revisión del diff que confirme que los checks no se eliminaron ni relajaron. | **NO SATISFECHO** — no se ha implementado ni ejecutado esta suite. |
| G4 | Los casos negativos demuestran que los detectores siguen disparando: call corta nueva, stack conocido excedido, `p` postflop, cobertura CM-004 incompleta y ledger alterado. | Pruebas negativas aisladas que fallan como se espera ante cada mutación, con resultados guardados; restauración del fixture/mutación sin cambiar datos canónicos. | **NO SATISFECHO** — no existen aún esas pruebas de mutación/negativas. |
| G5 | Snapshot histórico y base actual se mantienen distinguibles; ledger exacto; cierre del propietario. | Prueba de identidad/hash de ambos datasets, comparación exacta de ledger y aprobación explícita del propietario registrada después de G1–G4. | **NO SATISFECHO** — la comprobación documental del blob no sustituye la prueba implementada ni la firma de cierre. |

Solo después de que G1–G5 tengan evidencia y estado `SATISFECHO`, y de una instrucción explícita del propietario, se inicia PR-03. La implementación de la política es una tarea separada. Hasta entonces PR-03 permanece bloqueado.

---

## 6. Impacto sobre los 22 casos

### 6.1 Tabla actualizada

Leyenda: **A** snapshot histórico; **B** invariante dinámico; **C** cohorte; **D** fixture; **E** ledger/diagnóstico.

| # | Caso | Categoría anterior | Categoría resuelta (primaria / secundaria) | Cambio principal |
|---:|---|---|---|---|
| 1 | `test_la_base_de_hoy_ya_usa_p` | `CORREGIR_EXPECTATIVA_OBSOLETA` | B / A | 2522 al snapshot 1253; invariante actual de `p`; 2702 se reporta |
| 2 | `test_las_cifras_de_posiciones_estan_fijadas` | `CONVERTIR_A_INVARIANTE` | B / A | Invariantes de BB/posting/duplicados; conjunto exacto de 35 ausencias de SB |
| 3 | `test_un_jugador_sin_pos_es_uno_que_no_jugo` | `CONVERTIR_A_INVARIANTE` | B | `con_accion == 0`; 861 es diagnóstico |
| 4 | `test_no_hay_mesa_corta_ni_ante_ni_straddle` | `CONVERTIR_A_INVARIANTE` | B | 6 jugadores y postas 0.5/1.0; no se fija el total |
| 5 | `test_la_ciega_del_bb_que_existe_es_siempre_la_misma` | `CONVERTIR_A_INVARIANTE` | B | Importes 1.0/0.5 e índices; no se fijan 1253/1220 |
| 6 | `test_las_calls_que_no_llegan_a_la_viva` | `REQUIERE_DECISION_MANUAL` | E | Ledger: 41 all-in + 2 frames + 4 cortas reales; `H_0058` como fixture all-in |
| 7 | `test_el_patron_del_bb_es_exacto_no_aproximado` | `REQUIERE_DECISION_MANUAL` | `REEMPLAZAR_POR_INVARIANTE` / E | Se retira el par por orden; invariante por call + ledger; sin 60, −8, −28 ni −2 |
| 8 | `test_el_bote_exacto_cuadra_en_373_de_1253` | `CONSERVAR_SNAPSHOT` | A / B | Snapshot 1253 (373/3/877); invariante de partición actual + 3 IDs de `falta` |
| 9 | `test_el_rake_no_explica_el_bote` | `CONVERTIR_A_INVARIANTE` | B | Relación `con_rake < sin_rake`; los recuentos no se fijan y no son una partición |
| 10 | `test_aportar_mas_que_el_stack_no_depende_del_rake` | `REQUIERE_DECISION_MANUAL` | B / E | I4 conocido/desconocido/cero; 1 violación (`H_0740`) + 12 no evaluables; sin 12/13 |
| 11 | `test_el_json_y_el_informe_cuentan_lo_mismo` | `CONVERTIR_A_INVARIANTE` | B | Identidades con `s1['total']`; sin 1253/1344 |
| 12 | `test_el_invariante_de_cm004_puede_dispararse` | `CONVERTIR_A_INVARIANTE` | B | `con_ciega == len(manos)`; cobertura completa |
| 13 | `test_la_base_son_dos_grabadores` | `DEFINIR_SUBCONJUNTO` | C | Cohorte exacta de 71 IDs; live = total − cohorte |
| 14 | `test_la_apertura_cambia_tras_la_normalizacion` | `DEFINIR_SUBCONJUNTO` | C | Cohorte `hand` 31/29/4; live `c > r > b`; recuentos live se reportan |
| 15 | `test_las_42_calls_por_debajo_de_la_viva` | `REQUIERE_DECISION_MANUAL` | E | Total de calls derivado; ledger de cortas reales; 2832/47 se reportan |
| 16 | `test_la_falta_ya_no_es_dominante_pero_sigue_sin_ser_solo_del_bb` | `REQUIERE_DECISION_MANUAL` | B / E | `BB=2`, `CO=2`, `uno=3`; `BB < total` y `CO > 0`; se retira “seis posiciones” |
| 17 | `test_la_clasificacion_sobre_la_base` | `CONVERTIR_A_INVARIANTE` | B / E | Una clasificación por acción; ledger de sospechosas/indeterminadas; totales no fijados |
| 18 | `test_el_desglose_por_accion_por_resultado_es_coherente` | `CONVERTIR_A_INVARIANTE` | B | Coherencia fila/columna; matriz exacta no es contrato |
| 19 | `test_el_reparto_por_accion_suma_el_total_de_la_base` | `CONVERTIR_A_INVARIANTE` | B | `b+c+r == total`; `f/x` fuera; totales no fijados |
| 20 | `test_los_ids_se_resuelven_con_el_boton` | `REEMPLAZAR_POR_FIXTURE` | D / B | Fixtures de todos los asientos; invariante “todo ID de `allin` resuelve” |
| 21 | `test_por_defecto_cubre_toda_la_base` | `CONVERTIR_A_INVARIANTE` | B | `resumen['manos'] == len(manos)`; sin 1253 |
| 22 | `test_el_rango_por_defecto_sigue_siendo_toda_la_base` | `CONVERTIR_A_INVARIANTE` | B | Alcance total + `H_1282` dentro; sin 1253 |

### 6.2 Casos 6, 15 y 16: el mismo ledger, tres vistas

Los tres casos deben compartir **un único** detector y **un único** ledger:

- **Caso 6:** ledger de calls cortas con `tipo` (`ALLIN_CORTO`, `FRAME_INTERMEDIO`, `CORTA_CON_FICHAS`); `H_0058` como fixture literal.
- **Caso 15:** total de calls derivado de las acciones `c` parseables (2832); ledger de cortas reales (4); los 47 brutos se reportan.
- **Caso 16:** distribución de las cortas reales por posición; `BB=2`, `CO=2`, `uno=3`; propiedad `BB < total` y `CO > 0`.

No se actualiza 42→47 ni 2603→2832 en masa. El total bruto es un informe; el ledger es el contrato.

### 6.3 Caso 7: retirar la métrica de par

El test actual no protege una relación válida. La sustitución:

1. Para cada call, comprobar `amount` contra `viva_antes`; si no alcanza, clasificar con el helper.
2. Si se comparan SB y BB, hacerlo solo con la misma `viva_antes` y la misma calle; no usar la primera de cada lista.
3. Exigir que toda call sea `ALCANZA_VIVA`, `ALLIN_CORTO`, `FRAME_INTERMEDIO` o una entrada del ledger.
4. Reportar los pares de la misma viva como diagnóstico; no fijar 60.

Resultado esperado: `H_0104` y `H_1365` no forman pareja; `H_1310` es frame; no hay diferencias de par válidas. El −8 histórico no se conserva como “diferencia conocida”.

### 6.4 Caso 10: I4 con tres estados

El test debe distinguir:

- `I4_violaciones`: `H_0740` SB 28.2 > 28.1; 1.
- `I4_no_evaluable`: 12 IDs; incluye `H_1349`.
- `I4_cero_conocido`: conjunto vacío hoy; el contrato lo permite.
- `I2=3`, `I1=true`.

No se fija `I4=12` ni `I4=13`. La corrección del helper es parte de la implementación, no de este documento.

### 6.5 Casos 17, 18 y 19: el clasificador cambia con D2

La corrección del all-in acumulado afecta al clasificador. Estimación con el clasificador actual, reasignando los 41 all-in a `CALCULABLE`:

| Métrica | Actual | Estimado tras la corrección |
|---|---:|---:|
| `CALCULABLE` | 5417 | 5453 |
| `SOSPECHOSA` | 33 | 19 |
| `INDETERMINADA` | 26 | 4 |
| Total | 5476 | 5476 |
| Fila `b` | 1541/4 | 1541/4 |
| Fila `c` | 2781/25/26 | 2817/11/4 |
| Fila `r` | 1095/4 | 1095/4 |

La estimación no es un contrato: sirve para mostrar que **no se puede fijar 5417/33/26**. El contrato es:

- cada acción con dinero tiene exactamente una clasificación;
- la matriz suma por filas y columnas;
- `b+c+r` suma el total;
- el ledger de sospechosas/indeterminadas es exacto y revisado.

El valor exacto posterior a la corrección se recalcula y se revisa en la fase 5; no se actualiza a ciegas.

### 6.6 Caso 1: snapshot histórico + invariante actual

- **Snapshot 1253:** `p` total 2522; todas preflop; sin `p` postflop.
- **Actual:** toda `p` es preflop; toda SB/BB tiene `p` 0.5/1.0; no hay `p` en flop/turn/river; 2702 se reporta.
- **Negativo:** un `p` postflop, una ciega sin `p` o una posta con importe distinto falla.
- **Crecimiento:** una mano nueva con `p` legales pasa sin tocar el snapshot.

---

## 7. Implicaciones de implementación (no ejecutadas)

Esta sección describe lo que habría que hacer en una tarea posterior; no se ha hecho.

### 7.1 Helpers

- Un helper `aportado_acumulado` y una clasificación `ALLIN_CORTO` / `FRAME_INTERMEDIO` / `CORTA_CON_FICHAS` / `DESCONOCIDO`.
- `AO.seccion_3c`: sustituir `float(p.get('stack') or 0.0)` por un centinela `None` y separar `I4_violaciones` de `I4_no_evaluable`.
- `DG.calls_por_debajo`: usar la clasificación acumulada; no marcar `iguala_stack` solo por el importe de la acción.
- `DG.clasificar_aportado`: usar la misma clasificación para el all-in acumulado.
- Una sola definición de `viva`: máximo compromiso de la calle a partir de `p`/`b`/`r`, reinicio por calle; `c` no mueve la viva; una `c` por encima de la viva es una anomalía aparte.
- Una sola implementación de la comparación por call; retirar `seccion_2c` como contrato.

### 7.2 Tests

- Caso 1: snapshot 1253 + invariante actual.
- Caso 8: snapshot 1253 + partición actual + 3 IDs de `falta`.
- Casos 6/15/16: ledger compartido; `H_0058` fixture; distribución real.
- Caso 7: invariante por call + ledger; sin par por orden.
- Caso 10: I4 con tres estados.
- Casos 17/18/19: ledger + coherencia; sin totales fijados.
- Caso 20: fixtures de `get_position` + invariante de IDs resolubles.
- Casos 2/3/4/5/11/12/21/22: invariantes; sin literales de base.
- Casos 13/14: cohortes exactas; sin generalizar la huella `allin`.

### 7.3 Snapshot y ledger

- Crear el fixture `hands_1253_51a6fb9.jsonl` con su hash y manifiesto (fase 4).
- Crear el ledger de calls cortas/all-in/frames (fase 5).
- Crear el ledger de I4 no evaluable (12 IDs).
- Crear el ledger de clasificación sospechosa/indeterminada tras la corrección.
- Verificar el manifiesto `HANDS_DB_*` antes de medir.

### 7.4 Datos

- No se toca `data/hands_db.jsonl`.
- No se escribe 45.9 en `H_1349`.
- No se corrige `H_0740`, `H_0589`, `H_1287` ni `H_1310` para que pasen los tests.
- Cualquier corrección manual futura sigue el procedimiento de §4.6.

---

## 8. Riesgos y cuestiones abiertas

| Riesgo | Mitigación |
|---|---|
| El campo `allin` es incompleto (`H_1365` SB) | Usar la aritmética de stack; el campo solo corrobora |
| Un stack es erróneo y la clasificación all-in cambia | Si el stack es desconocido, `DESCONOCIDO`; si es conocido, el ledger registra la evidencia |
| El ledger se convierte en una lista de excusas | Gobierno D8: exactitud, revisión humana, nueva anomalía falla |
| El snapshot se confunde con la base actual | Fixture separado, hash verificado, marcador `snapshot` |
| El snapshot se duplica y envejece | Solo se crea cuando hay razón; el actual se lee por manifiesto |
| La corrección del clasificador cambia totales | `metrics_version` nueva; revisión y ledger; no auto-update |
| `H_0740` tiene tres síntomas | Registrar por separado; no sumar en un “defecto único” |
| `H_1310` sigue excluida de secuencia/frecuencias | Mantener la exclusión B1-E; el frame no la borra del registro |
| El ledger de frames se confunde con el de defectos | Tres clases separadas; solo `CORTA_CON_FICHAS` es anomalía de call |
| PR-03 se inicia antes de tiempo | Puerta G1–G5 y autorización explícita; este documento no autoriza |

Cuestiones que quedan para el propietario:

1. Ratificar el proceso D8 (aprobador, formato y flujo de alta/baja).
2. Autorizar o no PR-03 tras G1–G5.
3. Decidir si quiere un snapshot `canonical-1344` con censo 2702; la recomendación es no crearlo y usar el invariante.
4. Confirmar el formato exacto del ledger (JSON, YAML o módulo Python) en la fase 1.

---

## 9. Veredicto

Las decisiones D1–D7 y D9 quedan resueltas con evidencia. Las cinco manos que bloqueaban los casos 6, 7, 10, 15 y 16 tienen una lectura coherente:

- `H_1303` y `H_1365` son all-in por menos, no calls cortas defectuosas.
- `H_1310` son dos frames de una misma call, no dos defectos.
- `H_1349` es un stack desconocido, no un cero.
- `H_0104` es un all-in en otro nivel, no una diferencia de caja entre ciegas.
- Las únicas calls cortas reales son `H_0589`, `H_0740` (BB y CO) y `H_1287`.

El snapshot histórico debe ser el blob de `51a6fb9`, no un corte de las primeras 1253 líneas. La base actual sigue siendo dinámica y se lee por el manifiesto. Las correcciones manuales se preservan; el snapshot no se reescribe.

La suite puede diseñarse sin `REQUIERE_DECISION_MANUAL`. Lo que falta no es otra auditoría: es ratificar D8/D11 e implementar la política en una tarea separada. **PR-03 sigue bloqueado.**

---

## Anexo A. Listas exactas

### A.1 Manos sin SB (35)

```text
H_0035 H_0057 H_0158 H_0200 H_0240 H_0282 H_0294 H_0322 H_0365 H_0367
H_0391 H_0438 H_0511 H_0515 H_0531 H_0590 H_0594 H_0595 H_0596 H_0652
H_0716 H_0821 H_0833 H_0850 H_0908 H_0967 H_1041 H_1075 H_1106 H_1110
H_1138 H_1218 H_1248 H_1300 H_1369
```

Las 33 primeras son históricas; `H_1300` y `H_1369` son las nuevas.

### A.2 Cohorte `record_hand` (71)

```text
H_0001 H_0002 H_0003 H_0004 H_0005 H_0006 H_0007 H_0008 H_0009 H_0010
H_0011 H_0012 H_0013 H_0014 H_0015 H_0016 H_0017 H_0018 H_0019 H_0020
H_0021 H_0022 H_0023 H_0024 H_0025 H_0026 H_0027 H_0029 H_0030 H_0031
H_0032 H_0033 H_0034 H_0035 H_0036 H_0037 H_0038 H_0039 H_0040 H_0041
H_0042 H_0043 H_0044 H_0045 H_0046 H_0047 H_0048 H_0049 H_0050 H_0051
H_0052 H_0053 H_0054 H_0055 H_0056 H_0057 H_0058 H_0059 H_0060 H_0061
H_0062 H_0063 H_0064 H_0065 H_0066 H_0067 H_0068 H_0069 H_0070 H_0071
H_0073
```

### A.3 All-in por menos (41 actuales)

```text
H_0058 H_0084 H_0129 H_0130 H_0144 H_0145 H_0181 H_0185 H_0186 H_0188
H_0194 H_0205 H_0293 H_0311 H_0321 H_0351 H_0395 H_0441 H_0514 H_0527
H_0662 H_0708 H_0713 H_0757 H_0773 H_0906 H_0917 H_0926 H_0957 H_0963
H_0985 H_1041 H_1061 H_1068 H_1112 H_1118 H_1137 H_1150 H_1228 H_1303
H_1365
```

Los 39 históricos son esta lista menos `H_1303` y `H_1365`.

### A.4 Calls cortas reales (4 actuales)

```text
H_0589 preflop BB 5.9 / 6.9
H_0740 preflop BB 1.0 / 2.0
H_0740 preflop CO 1.0 / 2.0
H_1287 preflop CO 1.0 / 6.0
```

Las 3 históricas son las tres primeras.

### A.5 Frames intermedios (2)

```text
H_1310 preflop SB 1.0 / 3.0 -> final 3.0
H_1310 flop    SB 4.3 / 4.4 -> final 4.4
```

### A.6 Stacks desconocidos con aportación (12)

```text
H_0022 BB 1.0
H_0061 BB 1.0
H_0198 SB 0.5
H_0526 MP 1.0
H_0697 CO 1.0
H_0824 MP 2.5
H_0863 SB 0.5
H_0906 CO 114.0
H_0932 MP 131.3
H_1096 CO 12.7
H_1113 CO 15.0
H_1349 UTG 3.0
```

Los 11 históricos son los once primeros.

### A.7 Botes con `falta` (3)

```text
H_0357  aportado 3.5   final_pot 4.0   dif -0.5
H_0589  aportado 14.3  final_pot 15.0  dif -0.7
H_0740  aportado 36.8  final_pot 37.7  dif -0.9
```

### A.8 Valores del snapshot 1253

```text
manos                 1253
p total               2522 (todo preflop)
con_SB / sin_SB       1220 / 33
con_BB / sin_BB       1253 / 0
BB 1.0 / SB 0.5       1253 / 1220
n_jugadores           {6: 1253}
bote                  373 exactas / 3 falta / 877 sobra
rake                  373 sin / 268 con
I4                    12 = 1 real + 11 desconocidos
I2 / I1               3 / true
calls                 2603 total / 42 cortas (39 all-in + 3 reales)
clasificador          5001 / 29 / 23
matriz                5053
acciones b/c/r        1448 / 2603 / 1002
CM-004                1253 de 1253
lista saneamiento     1253, H_1282 presente
grabadores            1182 con allin / 71 sin allin
apertura hand         31 b / 29 c / 4 r
apertura live         100 b / 520 c / 467 r
allin resueltos       204 / 46 confirmados
```

---

## Anexo B. Estado de archivos y no modificación

- **Documentación de esta revisión:** `DOCS/RESOLUCION_DECISIONES_D1_D9_D11_2026-11-14.md` y la actualización de estado en `DOCS/POLITICA_MANTENIMIENTO_TESTS_BASE_DINAMICA_2026-11-14.md`.
- No se modificó `data/hands_db.jsonl`.
- No se modificaron tests.
- No se modificó código de producción ni herramientas.
- No se modificaron matrices, calibración, decisiones, observaciones, perfiles ni derivados.
- No se regeneraron artefactos.
- No se ejecutaron writers ni saneadores.
- No se redujo la base.
- No se actualizaron números en masa.
- No se creó commit de implementación de la política; la integración documental se realiza por instrucción explícita del propietario.
- No se inició PR-03.

Los cambios preexistentes de PR-02B siguen como estaban. El hash de `data/hands_db.jsonl` y de los artefactos de control es el de la política. Cualquier edición posterior de este documento cambia su hash.
