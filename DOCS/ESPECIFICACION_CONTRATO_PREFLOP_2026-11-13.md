# Especificación del contrato canónico preflop

**Fecha:** 2026-11-13  
**Estado:** especificación técnica consolidada para revisión  
**Ámbito:** clasificación y reconstrucción determinista de la primera decisión voluntaria preflop del héroe, y construcción de la consulta de rango asociada.  
**No implementa:** cambios en el motor, activación estratégica, soporte multiway ni modificaciones de datos históricos.

---

## 1. Objetivo y principios

Esta especificación define un contrato único para transformar los eventos preflop de una mano en:

1. Una secuencia normalizada de eventos.
2. Una reconstrucción del estado de apuestas anterior a la primera decisión voluntaria del héroe.
3. Una clasificación canónica de esa decisión.
4. Un plan de decisión preflop, cuando el estado sea resoluble.
5. Una consulta de rango independiente del plan.
6. Un estado explícito de cobertura de tablas y de incertidumbre.

El contrato debe producir el mismo resultado ante los mismos datos normalizados. No se permiten interpretaciones implícitas dependientes del consumidor.

### 1.1 Principios obligatorios

- Una acción histórica no debe reinterpretarse mediante heurísticas distintas en entrenamiento y serving.
- Las contribuciones al bote y las contribuciones a la apuesta vigente son magnitudes distintas.
- Un importe acumulado no debe confundirse con el incremento aportado en una acción.
- Una posta no es una acción voluntaria.
- Una anomalía de secuencia no equivale a una ausencia de cobertura.
- Un rango desconocido no equivale a un rango vacío ni a una probabilidad cero.
- La clasificación de la decisión no determina la disponibilidad de una tabla.
- Una consulta de rango no autoriza por sí misma una decisión.
- La falta de evidencia suficiente produce `unresolved`, `unknown` o `not_evaluated`, según el campo afectado.
- Ningún fallback aproximado debe presentarse como cobertura exacta.
- La implementación no debe inventar posiciones, importes, acciones, probabilidades ni rangos.

### 1.2 Fuera de alcance

Esta especificación no autoriza:

- Activar `MULTIWAY_SOPORTADO`.
- Cambiar la política estratégica del motor.
- Modificar `data/hands_db.jsonl`.
- Corregir automáticamente manos históricas.
- Regenerar matrices, perfiles o rangos.
- Modificar OCR, captura, recorder o pipeline de entrada.
- Ejecutar writers reales.
- Considerar una prueba mecánica como validación estratégica.

---

## 2. Modelo de datos

### 2.1 `PreflopAction`

Representa un evento ocurrido durante la fase preflop, después de su normalización.

Campos obligatorios:

| Campo | Tipo | Significado |
|---|---|---|
| `sequence_index` | entero | Índice de orden dentro de la secuencia normalizada |
| `player_id` | string o null | Identificador del jugador que origina el evento |
| `pos` | string o null | Posición del jugador, si está identificada |
| `raw_action` | string | Código original de la acción |
| `action` | string o null | Acción normalizada, si puede determinarse |
| `event_type` | enum | Naturaleza del evento |
| `amount` | decimal exacto o null | Contribución acumulada del jugador a la apuesta viva de la calle después del evento |
| `pot_contribution_delta` | decimal exacto o null | Incremento de dinero aportado al bote por ese evento |
| `amount_source` | string o null | Procedencia del importe normalizado |
| `amount_exactness` | enum | Grado de exactitud de los importes |
| `source_event_id` | string o null | Identificador del evento original |
| `metadata` | objeto | Evidencia adicional estructurada |

`amount` no representa el incremento de la acción ni el total histórico aportado al bote. Su significado es único: **contribución acumulada del jugador a la apuesta viva de la calle después del evento**.

### 2.2 Tipos de evento

`event_type` admite exclusivamente:

- `voluntary_action`
- `small_blind`
- `big_blind`
- `ante`
- `straddle`
- `dead_blind`
- `unknown_post`
- `unknown_event`

La clasificación del evento no depende del número de acciones voluntarias anteriores.

Un evento solo puede clasificarse como `small_blind`, `big_blind`, `ante`, `straddle` o `dead_blind` cuando exista evidencia suficiente en la fuente o en metadatos verificables.

No se permite clasificar un evento como posta únicamente por su importe, posición, orden o código aislado.

### 2.3 Acciones voluntarias

Cuando `event_type = voluntary_action`, `action` debe pertenecer al conjunto:

- `f`: fold.
- `x`: check.
- `c`: call.
- `b`: apuesta o acción de dinero identificada por la fuente como `b`.
- `r`: subida identificada por la fuente como `r`.

Los códigos originales se conservan en `raw_action`.

Si la fuente utiliza otros códigos, deben normalizarse mediante una tabla de conversión explícita y versionada. Un código desconocido no se transforma en una acción conocida por semejanza.

### 2.4 Representación de importes

Todos los importes se representan mediante decimales exactos o enteros en una unidad mínima definida.

Queda prohibido utilizar `float` binario como representación autoritativa para:

- Comparar importes.
- Calcular contribuciones.
- Determinar igualdad con `current_level`.
- Determinar si una subida supera el nivel vigente.
- Decidir si una acción es un limp corto.

La representación canónica debe conservar el valor original normalizado sin redondearlo silenciosamente.

---

## 3. Semántica de importes y contribuciones

### 3.1 Significado canónico de `amount`

`PreflopAction.amount` representa siempre la contribución acumulada del jugador a la apuesta viva de la calle después de procesar ese evento.

Ejemplo:

| Evento | `amount` anterior | `amount` posterior | Incremento |
|---|---:|---:|---:|
| SB publica 0.5 | 0 | 0.5 | 0.5 |
| SB completa hasta 1 | 0.5 | 1 | 0.5 |
| SB sube hasta 3 | 1 | 3 | 2 |

El incremento aportado se obtiene mediante:

\[
\Delta_{\text{live}} =
amount_{\text{posterior}} - amount_{\text{anterior}}
\]

No se suman importes acumulados sucesivos.

Si una fuente proporciona incrementos en lugar de importes acumulados, el adaptador de entrada debe convertirlos antes de construir `PreflopAction`.

### 3.2 Aportaciones al bote

`pot_contribution_delta` representa el dinero añadido al bote por el evento concreto.

Incluye:

- Ciegas.
- Antes.
- Straddles.
- Apuestas voluntarias.
- Calls.
- Raises.
- Otros pagos reconocidos.

Una acción sin aportación monetaria tiene `pot_contribution_delta = 0`.

Una acción cuyo importe monetario no puede determinarse tiene `pot_contribution_delta = null`, no cero.

`pot_contribution_delta` solo se calcula cuando la semántica del importe está establecida o demostrada. Si el importe es acumulado, el delta se obtiene como diferencia de contribución viva acumulada del jugador. Si el importe es un incremento, debe convertirse previamente a acumulado por el adaptador. Si la semántica es desconocida, no se inventa el delta: se conserva la fuente y se propaga `unknown`/`unresolved` en los campos derivados afectados.
### 3.3 Dinero vivo y dinero muerto

La contribución a la apuesta viva y la contribución al bote son magnitudes distintas.

- Las ciegas normales aumentan la contribución viva y el bote.
- Un straddle reconocido aumenta la contribución viva y el bote.
- Un ante aumenta el bote, pero no el nivel de apuesta viva.
- Una posta muerta aumenta el bote, pero no el nivel de apuesta viva.
- Una acción voluntaria de dinero aumenta ambas magnitudes.

Los antes no se utilizan para calcular `current_level` ni para determinar el importe que falta por igualar.

### 3.4 Normalización de fuentes

Cada adaptador debe declarar expresamente qué representa el importe original:

- `cumulative_after_event`: contribución acumulada después del evento.
- `increment_for_event`: incremento monetario de ese evento.
- `pot_payment_for_event`: pago al bote que no necesariamente es una apuesta viva.

La conversión se efectúa antes de crear `PreflopAction`.

Si el adaptador no puede distinguir entre estas representaciones, el importe normalizado queda `null` y la secuencia no puede utilizar ese valor como evidencia exacta.

No se permite que un consumidor vuelva a interpretar el importe original.

### 3.5 Contribuciones acumuladas por jugador

El normalizador mantiene, por jugador:

- `live_contribution`: aportación acumulada a la apuesta viva.
- `pot_contribution`: aportación acumulada al bote.

Para cada evento:

\[
live_{nuevo} = live_{anterior} + \Delta_{\text{live}}
\]

\[
pot_{nuevo} = pot_{anterior} + pot\_contribution\_delta
\]

La diferencia entre importes acumulados se calcula una sola vez. Ningún consumidor debe volver a sumar importes totales de acciones sucesivas.

### 3.6 Contribuciones del héroe

El contrato calcula por separado:

- `hero_contributed_pot`: aportación total conocida del héroe al bote.
- `hero_contributed_bet`: contribución acumulada del héroe a la apuesta viva de la calle.
- `hero_additional_to_call`: importe adicional necesario para igualar el nivel vigente.

La fórmula es:

\[
hero\_additional\_to\_call =
\max(0, current\_level - hero\_contributed\_bet)
\]

Esta fórmula solo puede utilizarse cuando los dos operandos están determinados exactamente.

Los antes y las postas muertas no se restan del importe pendiente por igualar.

Si una contribución del héroe es desconocida, el resultado correspondiente queda `null` y se identifica el motivo. No se sustituye por cero.

---

## 4. Identificación de ciegas, antes y straddles

### 4.1 Ciegas

Una ciega se reconoce mediante evidencia estructurada:

- Tipo de evento de la fuente.
- Identificador de apuesta forzada.
- Metadatos de posición y modalidad de la mesa.
- Registro explícito del proveedor.

La posición `SB` o `BB` por sí sola no demuestra que un evento sea una ciega.

`bb_posted = true` exclusivamente cuando se haya reconocido un evento `big_blind` válido y atribuido al jugador correspondiente.

Una acción de dinero realizada por un jugador en posición BB no basta para establecer `bb_posted`.

### 4.2 Antes

Un ante requiere evidencia que identifique el evento como aportación muerta.

El importe se incorpora a `pot_contribution_delta`, pero no aumenta `amount` ni `current_level`.

Se distinguen:

- Ante individual.
- Ante colectivo por jugador.
- Big blind ante.
- Ante muerto.

Un big blind ante no equivale a una ciega BB ordinaria. La parte correspondiente al ante se incorpora al bote como dinero muerto. Solo la parte identificada como ciega BB aumenta la apuesta viva.

Si la fuente no separa ambas cantidades, no se inventa la distribución.

### 4.3 Straddle

Un straddle reconocido debe disponer de:

- Identificador del jugador.
- Posición o asiento.
- Importe exacto.
- Modalidad de straddle.
- Evidencia de que la mesa permite esa posta.
- Evidencia de que la acción constituye un straddle vivo.

El importe del straddle aumenta la contribución viva y el bote.

Un importe superior a la BB no demuestra por sí mismo que sea un straddle.

Si la evidencia no permite distinguir un straddle de un post anómalo, se clasifica como `unknown_post`.

### 4.4 Posts desconocidos

Un código `p` siempre representa una posta o un evento de posta no clasificado. Nunca puede convertirse en una acción voluntaria.

Si no hay metadatos suficientes:

- `event_type = unknown_post`.
- Se conserva el importe original.
- No se actualiza `current_level` con ese importe.
- Se marca la secuencia como contaminada cuando el evento pueda afectar la reconstrucción.
- La decisión queda `unresolved` si la incertidumbre afecta al estado previo del héroe.

### 4.5 `blind_posts`

`blind_posts` contiene exclusivamente objetos de tipo `BlindPost`.

No contiene posiciones aisladas, acciones voluntarias ni antes genéricos.

Cada `BlindPost` debe incluir:

- `player_id`.
- `position`.
- `kind`.
- `amount`.
- `amount_exactness`.
- `source_event_id`.
- `recognized`.
- `recognition_reason`.

Un straddle se registra como evento de posta con su propio tipo. No se etiqueta como ciega BB.

---

## 5. Precisión y exactitud

### 5.1 Conceptos independientes

Se distinguen tres propiedades:

1. **Cuantización:** unidad mínima con la que la fuente representa el importe.
2. **Exactitud:** si el valor representa una cantidad exacta o una estimación.
3. **Incertidumbre:** intervalo de valores posibles cuando la fuente redondea o mide.

La cantidad de decimales escritos no determina por sí sola la precisión real.

### 5.2 `amount_exactness`

Valores permitidos:

- `exact`: el valor representa una cantidad exacta.
- `quantized_exact`: la fuente utiliza una unidad mínima conocida y el valor es exacto dentro de esa unidad.
- `rounded`: el valor fue redondeado y existe incertidumbre.
- `unknown`: no se conoce la exactitud.

Si el valor es `rounded`, debe conservarse el intervalo de incertidumbre o una descripción verificable de su origen.

`amount_type = observed` no demuestra por sí solo exactitud. Un importe observado puede ser redondeado, cuantizado o tener incertidumbre. No se marca `exact` o `quantized_exact` sin evidencia independiente de la precisión real de la fuente.
### 5.3 Comparaciones

Dos importes exactos se comparan después de convertirlos a una unidad común exacta.

Por ejemplo:

- `2.50` exacto y `2.5` exacto son iguales.
- `2.50` exacto y `2.500` exacto son iguales.
- `2.5` redondeado a una décima no se considera automáticamente igual a `2.50` exacto.

Si los intervalos de incertidumbre se solapan y no permiten decidir la relación, el resultado es `unresolved`.

Nunca se declara `precision_insufficient` únicamente porque dos cadenas tengan distinto número de decimales.

### 5.4 Uso en el contrato

Una cantidad con exactitud desconocida no puede utilizarse para resolver una igualdad crítica, un call, una subida o una contribución pendiente.

La incertidumbre se propaga a los campos derivados afectados.

No se redondea para forzar una clasificación.

---

## 6. Orden y validez de la secuencia

### 6.1 Datos de orden

Para evaluar el orden legal se necesitan:

- Número de jugadores sentados.
- Identificadores de asiento.
- Orden circular de asientos.
- Identificador del botón.
- Asignación de SB y BB.
- Posiciones efectivas.
- Modalidad de juego.
- Metadatos de straddle, si existe.
- Orden de eventos proporcionado por la fuente, si es autoritativo.

`players_at_table` no constituye por sí mismo un orden legal.

### 6.2 Fuentes de autoridad

Se admite una de estas dos vías:

1. Orden de actuación autoritativo suministrado por la fuente.
2. Reconstrucción a partir de asientos, botón, posiciones, reglas de mesa y modalidad de apuestas completamente identificados.

Si no se puede demostrar cuál es el siguiente jugador que debe actuar, el orden queda `not_evaluated`.

Una secuencia ordenada por la fuente no se considera automáticamente una secuencia legalmente validada. La fuente puede ser autoritativa para el orden de eventos, pero la validez legal exige comprobar el orden contra asientos, botón, posiciones y reglas. Si esa comprobación no se realiza, el resultado es `not_evaluated`, no `valid`.

No se marca una infracción por una mera ausencia de información.
### 6.3 Straddles y orden

El contrato solo valida automáticamente las modalidades de straddle cuyas reglas de orden estén explícitamente definidas.

Un straddle no estándar, múltiple, mississippi o modalidad especial sin reglas incorporadas produce `not_evaluated`.

No se extrapola el orden de un straddle convencional a modalidades diferentes.

### 6.4 Anomalías demostrables

Se consideran anomalías cuando existe evidencia suficiente de:

- Acción atribuida a un jugador que ya había foldeado.
- Acción duplicada incompatible con el estado.
- Evento sin jugador cuando la modalidad requiere atribución individual.
- Orden contrario al orden autoritativo.
- Acción posterior a un cierre inequívoco de la ronda.
- Contribución acumulada decreciente sin devolución o corrección documentada.

Las anomalías se registran con un código y evidencia. No se reparan automáticamente.

### 6.5 Estado de secuencia

Valores:

- `valid`: secuencia comprobada y coherente.
- `tainted`: existe una anomalía o ambigüedad que afecta a la reconstrucción.
- `not_evaluated`: no hay información suficiente para comprobar el orden.
- `incomplete`: la secuencia no contiene todos los eventos necesarios.

Una secuencia `not_evaluated` no equivale automáticamente a una secuencia inválida. Sin embargo, no puede utilizarse para afirmar que el orden fue validado.

---

## 7. Estado de apuestas

### 7.1 `current_level`

`current_level` es la mayor contribución viva válida establecida en la calle por:

- Ciegas reconocidas.
- Straddles reconocidos.
- Apuestas voluntarias válidas.
- Raises válidos.

No incluye antes ni postas muertas.

Una contribución de call no aumenta `current_level` si únicamente iguala el nivel vigente.

Un call all-in inferior al nivel vigente tampoco reduce `current_level`.

### 7.2 `last_aggressor_amount`

Es la contribución viva acumulada del último jugador que realizó una apuesta o subida agresiva válida.

Si no existe agresor:

- `last_aggressor_id = null`.
- `last_aggressor_amount = null`.

No se utilizan cadenas vacías ni cero como sustitutos de ausencia.

### 7.3 `mandatory_bet_to_call`

Es el importe adicional que el héroe necesita aportar para igualar `current_level`.

Se calcula con la contribución viva acumulada del héroe, no con su contribución total al bote.

Si el héroe está all-in, ya ha foldeado o no existe evidencia suficiente de su contribución, no se genera un importe de call operativo.

### 7.4 Calls

Un call ordinario debe terminar con una contribución viva acumulada igual a `current_level`.

Se permite un call inferior cuando la fuente identifica explícitamente un call all-in y la contribución es inferior al nivel vigente.

No se considera call una acción cuyo importe sea inferior por una diferencia inexplicada.

Las ciegas previas se descuentan al calcular el incremento necesario. No se contabilizan dos veces.

### 7.5 Raises

Una subida válida debe elevar `current_level`.

El contrato distingue:

- `raise_number`: número de subidas voluntarias válidas.
- `aggressive_action_count`: número de acciones agresivas válidas, incluidas las apuestas iniciales.
- `limp_count`: número de limps válidos.
- `call_count`: número de calls válidos.

Un limp no incrementa `raise_number`.

Una ciega, ante o straddle no incrementa `raise_number`.

Una acción agresiva cuyo importe no puede compararse exactamente deja los contadores afectados sin resolver.

---

## 8. Clasificación de la decisión preflop

### 8.1 Primera decisión voluntaria del héroe

La primera decisión voluntaria del héroe es el primer evento de tipo `voluntary_action` atribuido al héroe dentro de la secuencia preflop ordenada.

Los eventos de ciega, ante, straddle, post muerto y posta desconocida no son decisiones voluntarias.

El contrato no busca una decisión posterior del héroe para sustituir una primera decisión ausente.

Si no se puede identificar con certeza el primer evento voluntario del héroe, la decisión queda `unresolved`.

### 8.2 `PreflopDecision`

Campos principales:

| Campo | Significado |
|---|---|
| `status` | `resolved` o `unresolved` |
| `hero_id` | Identificador del héroe |
| `hero_position` | Posición del héroe |
| `hero_action_index` | Índice de su primera acción voluntaria |
| `prior_actions` | Eventos anteriores a esa acción |
| `decision_plan` | Clasificación canónica, si está resuelta |
| `range_query` | Consulta de rango independiente |
| `sequence_status` | Estado de la secuencia |
| `unresolved_reasons` | Motivos verificables de irresolución |

`PreflopDecision.status` admite `resolved`, `unresolved` y `no_decision`. `no_decision` se usa exclusivamente cuando no existe ninguna primera decisión voluntaria del héroe; no equivale a `unresolved`, que se reserva para una decisión que no pudo resolverse por falta de evidencia.

Si `status = no_decision`, no se genera `decision_plan`, `range_query`, etiqueta de entrenamiento ni acción de serving. `prior_actions` puede conservarse como prefijo observado, pero no se construye plan ni consulta.La naturaleza individual de un evento se expresa mediante `event_type`, no mediante un `status` inexistente en `PreflopAction`.

### 8.3 `prior_actions`

Contiene el prefijo de eventos anterior a la primera decisión voluntaria del héroe.

Incluye:

- Ciegas.
- Antes.
- Straddles.
- Posts reconocidos.
- Posts desconocidos.
- Acciones voluntarias de rivales.

No incluye la acción del héroe que se está clasificando.

El orden de `prior_actions` es el orden de la secuencia normalizada. No se ordena por importe.

### 8.4 Categorías canónicas

El contrato distingue, como mínimo:

- `OPEN`
- `LIMP`
- `CALL_LIMP`
- `FACING_OPEN`
- `FACING_3BET`
- `FACING_4BET`
- `ROL`
- `SQUEEZE`
- `CHECK_BB`
- `OTHER_RESOLVED`

La categoría se determina a partir de las acciones válidas anteriores a la decisión del héroe.

### 8.5 Reglas de clasificación

**OPEN**

Primera acción voluntaria agresiva que establece una apuesta inicial válida, sin limps ni subidas voluntarias anteriores.

**LIMP**

Primera acción voluntaria de dinero que iguala el nivel de la ciega sin subirlo, sin una subida voluntaria anterior.

**CALL_LIMP**

Call de un jugador después de uno o más limps y sin subida voluntaria previa.

**FACING_OPEN**

El héroe actúa frente a una subida inicial válida.

**FACING_3BET**

El héroe actúa frente a una tercera acción agresiva válida dentro de la secuencia de apuestas, según la convención de conteo documentada.

**FACING_4BET**

El héroe actúa frente a una cuarta acción agresiva válida.

**ROL**

Raise over limpers: subida válida después de uno o más limps y sin una subida agresiva previa.

**SQUEEZE**

Subida válida después de una subida inicial y al menos un call entre esa subida y la acción del héroe.

**CHECK_BB**

El héroe en BB realiza check cuando no existe una apuesta viva superior a su contribución y todos los jugadores activos anteriores han completado la acción requerida.

### 8.6 Casos no resolubles

Se usa `unresolved` cuando:

- No se conoce el importe necesario para determinar call o raise.
- Hay un post desconocido que afecta al nivel vigente.
- No se puede identificar el orden relevante de actuación.
- La secuencia presenta una anomalía que afecta al estado anterior al héroe.
- No se puede determinar qué acciones preceden a la decisión.
- Los eventos de apuestas no pueden distinguirse de forma fiable.

No se convierte un caso desconocido en `OPEN`, `LIMP` o `CALL` por aproximación.

---

## 9. Contadores y jugadores activos

### 9.1 Contadores

Todos los contadores se calculan a partir de eventos clasificados y validados.

Los eventos de posta no incrementan contadores de acciones voluntarias.

Los eventos desconocidos no se fuerzan dentro de una categoría.

Cada contador debe poder rastrearse hasta los índices de eventos que lo originaron.

### 9.2 `active_player_ids`

La fuente de verdad para jugadores activos es una colección de identificadores, no una lista de posiciones.

`active_positions` es una proyección derivada de `active_player_ids` y de las posiciones verificadas.

### 9.3 Transición transaccional

Cada evento se procesa en cuatro pasos:

1. Validar estructura, identidad, tipo de evento y coherencia con el estado actual.
2. Calcular los cambios propuestos sin modificar el estado vigente.
3. Comprobar que los cambios no violan invariantes.
4. Aplicar todos los cambios conjuntamente o no aplicar ninguno.

No se permite actualizar parcialmente el estado antes de completar la validación.

### 9.4 Fold

Un fold válido elimina al jugador de `active_player_ids`.

Un fold inválido no modifica la colección.

Un fold posterior a una contaminación no puede utilizarse para producir una nueva lista de jugadores activos fiable.

### 9.5 Contaminación

Cuando una acción contamina la secuencia:

- Se conserva el último estado fiable.
- Se marca `sequence_status = tainted`.
- Se congela la evolución de los estados derivados.
- Se conserva el evento problemático y su razón.
- No se procesan eventos posteriores como si el estado congelado fuera el estado actual real.

El estado congelado debe llevar `state_valid = false`.

No se presenta una lista congelada como `active_positions` actual y validada.

---

## 10. Contrato de rango

### 10.1 Separación de responsabilidades

`decision_plan` y `range_query` son objetos independientes.

`decision_plan` expresa qué situación preflop enfrenta el héroe.

`range_query` expresa qué tabla o rango se desea consultar para un jugador o situación.

La existencia de un plan no implica que exista un rango disponible.

La existencia de un rango no demuestra que la clasificación del plan sea correcta.

### 10.2 `RangeQuery`

Campos:

- `query_id`.
- `player_position`.
- `decision_category`.
- `table_key`.
- `status`.
- `source`.
- `reason`.
- `approximation_used`.

Estados permitidos:

- `available`
- `no_range`
- `no_table`
- `unresolved`
- `not_applicable`

`available` significa que existe una fuente utilizable identificada.

`no_range` significa que la consulta es válida, pero no existe un rango definido.

`no_table` significa que no existe una tabla para esa clave.

`unresolved` significa que no puede construirse la consulta de forma fiable.

`not_applicable` significa que la consulta no corresponde a esa situación.

Un rango vacío no se interpreta como probabilidad cero.

### 10.3 Plan sin rango

Una decisión puede tener `status = resolved` y una consulta con `no_table`.

Eso no autoriza a sustituir automáticamente la tabla ausente por otra situación.

La política de serving debe decidir explícitamente si puede mostrar una recomendación sin respaldo de rango.

---

## 11. Cobertura de tablas

### 11.1 Estados por consulta

Cada consulta de cobertura tiene uno de estos estados:

- `exact`
- `alias`
- `coverage_gap`
- `impossible`
- `unknown`

**Exact:** existe una tabla específica para la clave solicitada.

**Alias:** existe una equivalencia documentada y validada con otra clave.

**Coverage gap:** la consulta es válida, pero no hay cobertura directa ni equivalencia aprobada.

**Impossible:** la consulta no corresponde a una situación posible bajo el contrato.

**Unknown:** no hay evidencia suficiente para determinar la cobertura.

`fallback_other_vs` se clasifica como `coverage_gap` con aproximación explícita. Nunca como cobertura exacta.

### 11.2 Agregación de varias consultas

La agregación no debe ocultar estados individuales.

Se conservan siempre `coverage.queries[]` y sus resultados.

El resumen agregado admite:

- `complete_exact`: todas las consultas aplicables son exactas.
- `complete_with_alias`: todas están cubiertas, pero al menos una utiliza alias.
- `partial`: existe al menos una consulta cubierta y otra con gap o unknown.
- `none_applicable`: todas las consultas son impossible o not_applicable.
- `unknown`: ninguna conclusión fiable puede obtenerse.
- `unresolved`: la construcción de las consultas no pudo completarse.

### 11.3 Reglas de combinación

| Combinación de consultas | Resultado agregado |
|---|---|
| exact + exact | `complete_exact` |
| exact + alias | `complete_with_alias` |
| alias + alias | `complete_with_alias` |
| exact + coverage_gap | `partial` |
| alias + coverage_gap | `partial` |
| exact + unknown | `partial` |
| alias + unknown | `partial` |
| impossible + exact | `complete_exact` sobre consultas aplicables |
| impossible + alias | `complete_with_alias` sobre consultas aplicables |
| impossible + coverage_gap | `partial` |
| impossible + unknown | `partial` |
| impossible + impossible | `none_applicable` |
| unknown + unknown | `unknown` |
| unresolved en construcción | `unresolved` |

Las consultas `impossible` no cuentan como consultas aplicables y no invalidan una cobertura exacta de las consultas que sí corresponden.

Si una consulta está marcada `unknown`, no puede afirmarse cobertura completa.

### 11.4 Regla de fallback

Un fallback solo se permite si existe una política explícita que indique:

- Qué clave se utiliza.
- Por qué es una aproximación aceptable.
- Qué diferencias tiene respecto a la consulta original.
- Qué consumidores pueden utilizarlo.
- Cómo se informa su incertidumbre.

Un fallback no cambia el estado original `coverage_gap`.

---

## 12. Invariantes del contrato

La implementación debe respetar todos estos invariantes:

1. `amount` siempre representa contribución acumulada viva después del evento.
2. `pot_contribution_delta` siempre representa el incremento aportado al bote por el evento.
3. Un ante no aumenta `current_level`.
4. Un post desconocido no se convierte en acción voluntaria.
5. `p` nunca se procesa como call, bet o raise.
6. `bb_posted` requiere una ciega BB reconocida.
7. `raise_number` no incluye limps ni posts.
8. Un call ordinario iguala el nivel vigente.
9. Un call all-in corto requiere evidencia explícita.
10. Las contribuciones acumuladas no se suman como incrementos.
11. Una comparación crítica de importes requiere exactitud suficiente.
12. `PreflopDecision.status` admite `resolved`, `unresolved` o `no_decision`; `no_decision` no equivale a `unresolved`.
13. La clasificación de un evento pertenece a `event_type`.14. `prior_actions` es un prefijo ordenado anterior a la primera decisión voluntaria del héroe.
15. No se deduce orden legal de una lista sin orden de asientos.
16. Un estado contaminado no produce nuevas transiciones fiables.
17. `active_positions` nunca se presenta como estado fiable después de congelarse.
18. `decision_plan` y `range_query` permanecen separados.
19. Un `coverage_gap` no se convierte en `exact` por fallback.
20. Un rango vacío no se interpreta como probabilidad cero.
21. `unknown`, `unresolved`, `impossible` y `not_applicable` no son intercambiables.
22. La ausencia de evidencia no se interpreta como evidencia de ausencia.
23. Ningún consumidor recalcula una semántica distinta para los mismos campos.
24. Las reglas de clasificación son idénticas para entrenamiento, auditoría y serving.

---

## 13. Algoritmo normativo

El procesamiento debe realizarse en este orden:

### Paso 1. Normalización

- Conservar eventos originales.
- Normalizar códigos de acción.
- Normalizar importes según la semántica declarada de la fuente.
- Asignar `event_type` mediante evidencia explícita.
- Conservar exactitud, origen y metadatos.
- No inventar valores ausentes.

### Paso 2. Validación estructural

Comprobar:

- Identificadores.
- Orden disponible.
- Tipos de evento.
- Importes.
- Coherencia entre jugador, posición y evento.
- Integridad de los metadatos.

Registrar errores sin corregirlos automáticamente.

### Paso 3. Validación de secuencia

Determinar si el orden es:

- `valid`
- `tainted`
- `not_evaluated`
- `incomplete`

No reconstruir un orden legal sin evidencia suficiente.

### Paso 4. Reconstrucción de apuestas

Procesar cada evento de manera transaccional.

Actualizar:

- Contribución viva por jugador.
- Contribución al bote por jugador.
- `current_level`.
- Último agresor.
- Contadores.
- Jugadores activos.

Si aparece contaminación, congelar el último estado fiable.

### Paso 5. Identificación del héroe

Encontrar la primera acción voluntaria del héroe.

Si no puede identificarse de manera inequívoca, devolver `unresolved`.

### Paso 6. Construcción del prefijo

Construir `prior_actions` con todos los eventos anteriores a la primera acción voluntaria del héroe.

No incluir esa acción ni eventos posteriores.

### Paso 7. Clasificación

Determinar `decision_plan` a partir del prefijo y del estado reconstruido.

Si falta evidencia necesaria, no asignar una categoría aproximada.

### Paso 8. Consulta de rango

Construir `range_query` solo cuando la situación permita identificar la clave solicitada.

No alterar el plan para ajustarlo a una tabla existente.

### Paso 9. Cobertura

Consultar cobertura por clave y producir estados individuales y agregado.

Conservar cualquier fallback como aproximación.

### Paso 10. Resultado

Devolver:

- Estado global.
- Plan, si existe.
- Prefijo.
- Estado de apuestas.
- Contribuciones.
- Consulta de rango.
- Cobertura.
- Motivos de incertidumbre.
- Evidencia y procedencia.

---

## 14. Ejemplos normativos

Los importes de esta sección son unidades exactas y las secuencias se consideran completas, salvo que se indique lo contrario.

### 14.1 SB completa hasta BB

Eventos:

| Índice | Jugador | Evento | `amount` |
|---:|---|---|---:|
| 0 | SB | `small_blind` | 0.5 |
| 1 | BB | `big_blind` | 1.0 |
| 2 | SB | `voluntary_action/c` | 1.0 |

Resultado:

- Incremento de la SB al completar: 0.5.
- Contribución viva acumulada SB: 1.0.
- Contribución viva acumulada BB: 1.0.
- `current_level`: 1.0.
- No se contabiliza 0.5 + 1.0 como contribución de la SB.

### 14.2 Ante individual seguido de apuesta

Eventos:

| Índice | Jugador | Evento | `amount` | `pot_contribution_delta` |
|---:|---|---|---:|---:|
| 0 | H | `ante` | 0 | 0.1 |
| 1 | V | `ante` | 0 | 0.1 |
| 2 | V | `voluntary_action/b` | 2.0 | 2.0 |

Resultado:

- Ante de H: 0.1 al bote.
- Contribución viva de H: 0.
- `current_level`: 2.0.
- Importe adicional de H para igualar: 2.0.
- El ante no reduce el call pendiente.

### 14.3 Big blind ante

Si la fuente identifica por separado:

- BB ordinaria: 1.0.
- Ante BB: 0.5.

El resultado es:

- Contribución viva BB: 1.0.
- Contribución al bote BB: 1.5.
- `current_level`: 1.0.

Si la fuente solo informa un pago de 1.5 sin desglose, no se decide que 1.0 sea ciega y 0.5 ante por inferencia.

### 14.4 Straddle reconocido

Un straddle vivo de 2.0, con evidencia explícita:

- Aumenta la contribución viva del jugador a 2.0.
- Aumenta el bote en 2.0.
- Establece `current_level = 2.0`, si no existe una apuesta viva superior.
- No incrementa `raise_number`.
- No se clasifica como acción voluntaria.

### 14.5 Post superior a BB no reconocido

Una acción de 3.0 desde una posición cualquiera, sin metadatos de straddle ni otra evidencia:

- `event_type = unknown_post`, si la fuente identifica el evento como posta.
- No se clasifica como raise.
- No actualiza `current_level`.
- Contamina la reconstrucción si afecta al estado previo del héroe.

El importe por sí solo no autoriza a clasificarlo como straddle.

---

## 15. Matriz de pruebas de aceptación

Los siguientes casos son pruebas normativas. Los resultados deben reproducirse con el mismo conjunto de eventos normalizados.

| ID | Entrada | Resultado esperado |
|---|---|---|
| T01 | SB 0.5; BB 1.0; SB completa hasta `amount=1.0` | Incremento SB 0.5; contribución viva SB 1.0; nivel 1.0 |
| T02 | BB publica 1.0 y después hace check | `bb_posted=true`; check voluntario; nivel 1.0 |
| T03 | H paga ante 0.1; no realiza apuesta | Bote +0.1; contribución viva H 0 |
| T04 | BB ante separado 0.5 y ciega BB 1.0 | Bote +1.5; contribución viva 1.0; nivel 1.0 |
| T05 | Straddle 2.0 reconocido | Evento straddle; contribución viva 2.0; nivel 2.0; no incrementa `raise_number` |
| T06 | Post 3.0 sin metadatos de straddle | `unknown_post`; no se clasifica como raise; estado afectado unresolved |
| T07 | Jugador pasa de 0.5 a 1.0 y luego a 3.0 | Incrementos 0.5 y 2.0; contribución acumulada final 3.0 |
| T08 | SB 0.5; nivel 1.0; SB hace call hasta `amount=1.0` | Incremento 0.5; call válido; no doble conteo |
| T09 | BB 1.0; nivel 2.0; BB hace call hasta `amount=2.0` | Incremento 1.0; call válido |
| T10 | Fuente A informa acumulado 3.0; fuente B informa incremento 2.0 desde 1.0 | Ambos normalizan a acumulado 3.0 |
| T11 | 2.50 exacto frente a 2.5 exacto | Igualdad exacta |
| T12 | 2.5 redondeado a décimas frente a 2.50 exacto, sin intervalo que permita igualdad | Comparación unresolved |
| T13 | Botón, asientos, SB, BB y orden autoritativo conocidos; secuencia legal | `sequence_status=valid` |
| T14 | Mismos datos, pero un jugador actúa antes de quien debe actuar según orden autoritativo | `sequence_status=tainted`; código de orden incompatible |
| T15 | Falta botón y orden autoritativo | `sequence_status=not_evaluated`; no declarar infracción |
| T16 | Fold válido; evento posterior imposible de validar | Conservar último estado fiable; congelar estado derivado; `state_valid=false` |
| T17 | Acción `p` sin metadatos suficientes | `unknown_post`; nunca `voluntary_action` |
| T18 | `exact` + `impossible` en consultas | `complete_exact` sobre consultas aplicables |
| T19 | `exact` + `coverage_gap` | Agregado `partial`; conservar ambos estados |
| T20 | `alias` + `exact` | `complete_with_alias` |
| T21 | Todas las consultas `impossible` | `none_applicable` |
| T22 | Consulta con `fallback_other_vs` | `coverage_gap` con aproximación explícita |
| T23 | H paga ante y después hace call | Ante solo al bote; call calculado contra contribución viva |
| T24 | Jugador realiza varias acciones de dinero | Contribución acumulada calculada por diferencias, sin sumar importes totales |
| T25 | Acción con importe desconocido que afecta al nivel | Decisión unresolved; no generar call ni raise inventado |

### 15.1 Datos mínimos por prueba

Cada prueba debe contener:

- Identificador de mano sintético o fixture.
- Identificadores de jugadores.
- Posiciones y asientos, cuando correspondan.
- Botón y orden, cuando correspondan.
- Eventos completos en orden.
- Importe original y semántica de fuente.
- Importe normalizado.
- Exactitud del importe.
- Metadatos de posts.
- Estado inicial.
- Resultado esperado.
- Motivo de aceptación o rechazo.

No se acepta una prueba que solo contenga una descripción narrativa sin entradas suficientes para reproducir el resultado.

### 15.2 Separación de pruebas

Las pruebas se dividen en:

- Pruebas de normalización.
- Pruebas de clasificación de eventos.
- Pruebas de secuencia.
- Pruebas de contribuciones.
- Pruebas de clasificación preflop.
- Pruebas de cobertura.
- Pruebas de incertidumbre.
- Pruebas de integración entre contrato y consumidores.

Los fixtures sintéticos deben permanecer separados de los datos históricos reales.

---

## 16. Migración y compatibilidad

La adopción del contrato no debe reinterpretar silenciosamente datos históricos.

Antes de migrar un consumidor:

1. Identificar su interpretación actual de cada campo.
2. Identificar su fuente de datos.
3. Comparar su semántica con la de este contrato.
4. Construir pruebas de paridad.
5. Identificar registros que no pueden normalizarse.
6. Mantener esos registros en estado unresolved o quarantine.
7. Definir rollback.
8. Ejecutar primero en sombra.

No se debe modificar el histórico para forzar compatibilidad.

Los consumidores antiguos pueden permanecer temporalmente, pero deben identificarse como legacy y no presentarse como equivalentes al contrato canónico.

### 16.1 Rollback

Toda migración de un consumidor debe permitir volver a la implementación anterior sin:

- Cambiar los datos originales.
- Perder procedencia.
- Regenerar derivados automáticamente.
- Cambiar el estado de soporte multiway.
- Activar serving de una política experimental.

El rollback debe probarse antes de cualquier activación.

---

## 17. Criterios de aceptación de la especificación

La especificación se considera implementable solo cuando se cumplan todos los puntos:

1. Cada campo tiene tipo, semántica, fuente y regla de cálculo.
2. `amount` tiene una única semántica en todo el contrato.
3. Las fuentes que informan incrementos se normalizan antes de construir eventos.
4. Las contribuciones vivas y al bote se mantienen separadas.
5. Los posts se identifican por evidencia explícita.
6. Un evento `p` nunca se transforma en acción voluntaria.
7. Los straddles requieren evidencia suficiente.
8. `bb_posted` solo reconoce una ciega BB válida.
9. Las comparaciones respetan exactitud e incertidumbre.
10. El orden solo se valida cuando existe evidencia suficiente.
11. Las transiciones de estado son deterministas y transaccionales.
12. La contaminación congela el estado derivado.
13. La primera decisión voluntaria del héroe se identifica sin campos inexistentes.
14. `decision_plan` y `range_query` permanecen separados.
15. La cobertura individual y agregada tiene reglas completas.
16. Los fallbacks no se presentan como cobertura exacta.
17. Los ejemplos y pruebas derivan de las reglas escritas.
18. La matriz contiene entradas suficientes para reproducir cada resultado.
19. La implementación puede rechazar casos desconocidos sin inventar una clasificación.
20. Entrenamiento, auditoría y serving utilizan la misma semántica.

---

## 18. Restricciones de implementación y activación

Esta especificación no constituye autorización de implementación ni de activación.

Cualquier implementación posterior deberá:

- Comenzar con pruebas unitarias del normalizador.
- Mantener datos originales inmutables durante la migración.
- Ejecutarse inicialmente en sombra.
- Registrar discrepancias entre el contrato y los consumidores legacy.
- Mantener `MULTIWAY_SOPORTADO = False`.
- No convertir una reconstrucción HU en una solución MW.
- No utilizar `RangeState.union()` como distribución conjunta multiway.
- No declarar validez estratégica por el mero hecho de pasar pruebas mecánicas.

La activación requerirá una validación estratégica independiente, con escenarios de referencia, evaluación fuera de muestra, incertidumbre cuantificada y autorización explícita.

**Fin de la especificación.**